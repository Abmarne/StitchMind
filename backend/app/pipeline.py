import re
import json
import datetime
from sqlalchemy.orm import Session
from app.database import Document, EntityLink, Connector
from app.vector_store import add_chunks, delete_chunks_by_document, search_similar_chunks
from app.embedder import get_embedding
from app.config import GEMINI_API_KEY, OLLAMA_HOST
import litellm

# Configure litellm logger to avoid excessive debug outputs
litellm.logging = False

# Regex patterns for deterministic linking
# Matches keys like APP-123 or SEC-999
JIRA_PATTERN = re.compile(r'\b([A-Z]{2,10})-\d+\b')
# Matches references to pull requests like PR #40 or pull request 22
GITHUB_PR_PATTERN = re.compile(r'\b(?:pull request|pr|pull|#)\s*#?(\d+)\b', re.IGNORECASE)

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """Splits a document's body into sliding text chunks."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def run_regex_linking(db: Session, doc: Document):
    """Scans document text for entity codes and links them to other items in SQLite."""
    text_content = f"{doc.title or ''} {doc.body or ''}"
    
    # 1. Jira Ticket References
    jira_matches = JIRA_PATTERN.findall(text_content)
    for match in set(jira_matches):
        ticket_id = match.upper()
        # Find matching Jira documents in database (exclude self)
        target_docs = db.query(Document).filter(
            Document.external_id == ticket_id,
            Document.id != doc.id
        ).all()
        for target in target_docs:
            exists = db.query(EntityLink).filter(
                ((EntityLink.source_doc_id == doc.id) & (EntityLink.target_doc_id == target.id)) |
                ((EntityLink.source_doc_id == target.id) & (EntityLink.target_doc_id == doc.id))
            ).first()
            if not exists:
                new_link = EntityLink(
                    source_doc_id=doc.id,
                    target_doc_id=target.id,
                    link_type="regex_match",
                    confidence=1.0,
                    description=f"Jira Key '{ticket_id}' referenced in document text."
                )
                db.add(new_link)

    # 2. GitHub PR References
    pr_matches = GITHUB_PR_PATTERN.findall(text_content)
    for match in set(pr_matches):
        pr_id = str(match)
        # Find GitHub pull request documents
        target_docs = db.query(Document).filter(
            Document.platform == "github",
            Document.external_id == pr_id,
            Document.id != doc.id
        ).all()
        for target in target_docs:
            exists = db.query(EntityLink).filter(
                ((EntityLink.source_doc_id == doc.id) & (EntityLink.target_doc_id == target.id)) |
                ((EntityLink.source_doc_id == target.id) & (EntityLink.target_doc_id == doc.id))
            ).first()
            if not exists:
                new_link = EntityLink(
                    source_doc_id=doc.id,
                    target_doc_id=target.id,
                    link_type="regex_match",
                    confidence=0.9,
                    description=f"GitHub PR #{pr_id} referenced in document text."
                )
                db.add(new_link)
                
    db.commit()

def process_and_index_document(
    db: Session, 
    connector_id: int, 
    external_id: str, 
    platform: str, 
    title: str, 
    body: str, 
    url: str = None, 
    author: str = None, 
    created_at: datetime.datetime = None
) -> Document:
    """Processes, chunks, embeds, vector-stores, and links a document."""
    # 1. Upsert metadata in SQLite
    doc = db.query(Document).filter(
        Document.platform == platform,
        Document.external_id == external_id
    ).first()
    
    if doc:
        doc.title = title
        doc.body = body
        doc.url = url
        doc.author = author
        doc.synced_at = datetime.datetime.utcnow()
        if created_at:
            doc.created_at = created_at
        if connector_id:
            doc.connector_id = connector_id
    else:
        doc = Document(
            connector_id=connector_id,
            external_id=external_id,
            platform=platform,
            title=title,
            body=body,
            url=url,
            author=author,
            created_at=created_at or datetime.datetime.utcnow(),
            synced_at=datetime.datetime.utcnow()
        )
        db.add(doc)
    
    db.commit()
    db.refresh(doc)
    
    # 2. Re-index vector chunks in LanceDB
    delete_chunks_by_document(doc.id)
    
    chunks = chunk_text(body)
    if chunks:
        from app.embedder import get_embeddings
        try:
            embeddings = get_embeddings(chunks)
            lancedb_chunks = []
            for idx, (chunk_txt, vector) in enumerate(zip(chunks, embeddings)):
                lancedb_chunks.append({
                    "id": f"{doc.id}_{idx}",
                    "document_id": doc.id,
                    "chunk_index": idx,
                    "text": chunk_txt,
                    "vector": vector,
                    "platform": platform,
                    "url": url or "",
                    "title": title or ""
                })
            add_chunks(lancedb_chunks)
        except Exception as e:
            print(f"Error vector-indexing document {doc.id}: {e}")
            
    # 3. Form graph links
    run_regex_linking(db, doc)
    
    return doc

def unify_context(db: Session, doc_id: int, use_local_llm: bool = False, local_model: str = "llama3") -> dict:
    """Gathers structured & semantic context relative to a document and summarizes it with an LLM."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return {"error": "Document not found"}
        
    # 1. Fetch relational links from SQLite
    links = db.query(EntityLink).filter(
        (EntityLink.source_doc_id == doc.id) | (EntityLink.target_doc_id == doc.id)
    ).all()
    
    linked_docs = []
    seen_ids = {doc.id}
    for link in links:
        other_doc_id = link.target_doc_id if link.source_doc_id == doc.id else link.source_doc_id
        if other_doc_id not in seen_ids:
            seen_ids.add(other_doc_id)
            other_doc = db.query(Document).filter(Document.id == other_doc_id).first()
            if other_doc:
                linked_docs.append({
                    "platform": other_doc.platform,
                    "title": other_doc.title,
                    "author": other_doc.author,
                    "url": other_doc.url,
                    "body_snippet": other_doc.body[:300] + "..." if other_doc.body else "",
                    "link_reason": link.description
                })

    # 2. Fetch semantic matches from LanceDB using title embeddings
    semantic_chunks = []
    try:
        title_vector = get_embedding(f"{doc.title or ''} {doc.body[:200] if doc.body else ''}")
        # Retrieve top 5 semantic chunks
        results = search_similar_chunks(title_vector, limit=5)
        for chunk in results:
            if chunk["document_id"] not in seen_ids:
                # Add to context
                semantic_chunks.append({
                    "platform": chunk["platform"],
                    "title": chunk["title"],
                    "text": chunk["text"],
                    "url": chunk["url"]
                })
    except Exception as e:
        print(f"Error gathering semantic matches for doc {doc.id}: {e}")

    # 3. Assemble Prompt
    system_prompt = (
        "You are StitchMind's Context Unifier. You analyze scattered info across work platforms "
        "(Slack, GitHub, Jira, Gmail, Docs) and present it in a clean, unified view. "
        "Your goal is to explain how these items connect, point out anomalies (like status mismatches), "
        "and suggest the user's next logical steps.\n"
        "You MUST output raw JSON matching this schema:\n"
        "{\n"
        "  \"summary\": \"Concise paragraph linking the conversations and documents together.\",\n"
        "  \"anomalies\": \"Any warning or mismatch (e.g. Jira says open, but Slack chat says merged). Empty string if none.\",\n"
        "  \"suggested_actions\": [\n"
        "     { \"label\": \"Action name (e.g., Approve PR #24)\", \"action_type\": \"github_pr_view/jira_update/slack_reply/etc\", \"url\": \"link if applicable\", \"payload\": {} }\n"
        "  ]\n"
        "}"
    )

    prompt = (
        f"TARGET DOCUMENT:\n"
        f"Platform: {doc.platform.upper()}\n"
        f"Title: {doc.title}\n"
        f"Author: {doc.author}\n"
        f"URL: {doc.url}\n"
        f"Content: {doc.body}\n\n"
    )
    
    if linked_docs:
        prompt += "RELATIONALLY LINKED DOCUMENTS (Hard matches):\n"
        for idx, ld in enumerate(linked_docs):
            prompt += (
                f"- Link [{idx+1}]: Platform: {ld['platform'].upper()}, Title: {ld['title']}, "
                f"Link Reason: {ld['link_reason']}\n"
                f"  Snippet: {ld['body_snippet']}\n"
            )
        prompt += "\n"
        
    if semantic_chunks:
        prompt += "SEMANTICALLY RELATED FRAGMENTS (Found via vector search):\n"
        for idx, sc in enumerate(semantic_chunks):
            prompt += (
                f"- Semantic [{idx+1}]: Platform: {sc['platform'].upper()}, Title: {sc['title']}\n"
                f"  Snippet: {sc['text']}\n"
            )
        prompt += "\n"

    # 4. Trigger LLM Completion
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    try:
        if use_local_llm:
            # Call local Ollama
            response = litellm.completion(
                model=f"ollama/{local_model}",
                messages=messages,
                api_base=OLLAMA_HOST,
                response_format={"type": "json_object"}
            )
        else:
            # Call Google Gemini 1.5 Flash (default)
            if not GEMINI_API_KEY:
                # Fallback to local Ollama if key missing
                print("Gemini API key missing, falling back to Ollama")
                response = litellm.completion(
                    model=f"ollama/{local_model}",
                    messages=messages,
                    api_base=OLLAMA_HOST,
                    response_format={"type": "json_object"}
                )
            else:
                response = litellm.completion(
                    model="gemini/gemini-1.5-flash",
                    messages=messages,
                    api_key=GEMINI_API_KEY,
                    response_format={"type": "json_object"}
                )
                
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error in LLM context unification completion: {e}")
        # Return fallback mock JSON to ensure the app doesn't crash
        return {
            "summary": f"Analyzed {doc.title}. Found {len(linked_docs)} direct relationships and {len(semantic_chunks)} semantic matches.",
            "anomalies": "Unable to complete AI analysis. Check your Gemini API key or local Ollama configuration.",
            "suggested_actions": [
                {
                    "label": f"Open original {doc.platform.upper()} resource",
                    "action_type": "open_url",
                    "url": doc.url or "#"
                }
            ]
        }
