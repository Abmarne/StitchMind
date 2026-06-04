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
JIRA_PATTERN = re.compile(r'\b([A-Z]{2,10}-\d+)\b')
# Matches references to pull requests like PR #40 or pull request 22
GITHUB_PR_PATTERN = re.compile(r'\b(?:pull request|pr|pull|#)\s*#?(\d+)\b', re.IGNORECASE)
URL_PATTERN = re.compile(r'https?://[^\s)\]]+', re.IGNORECASE)
BRANCH_PATTERN = re.compile(r'\bbranch\s+([a-z0-9._/-]+)\b', re.IGNORECASE)

def infer_intent(doc: Document) -> str:
    """Classifies a document into a workflow type using transparent local rules."""
    text_content = f"{doc.title or ''} {doc.body or ''}".lower()
    if any(term in text_content for term in ["flight", "hotel", "itinerary", "check-in", "booking"]):
        return "personal_logistics"
    if any(term in text_content for term in ["epic", "sprint", "milestone", "roadmap", "launch", "planning"]):
        return "project_planning"
    if any(term in text_content for term in ["incident", "outage", "severity", "regression"]):
        return "incident"
    if any(term in text_content for term in ["bug", "fix", "pr #", "pull request", "jira", "token", "error"]):
        return "bug_tracking"
    if any(term in text_content for term in ["approved", "decision", "decided", "sign-off"]):
        return "decision"
    return "general_context"

def create_entity_link(
    db: Session,
    source_doc_id: int,
    target_doc_id: int,
    link_type: str,
    confidence: float,
    description: str
):
    """Creates one undirected graph edge if the same pair/type does not already exist."""
    if source_doc_id == target_doc_id:
        return
    exists = db.query(EntityLink).filter(
        (
            (EntityLink.source_doc_id == source_doc_id) &
            (EntityLink.target_doc_id == target_doc_id) &
            (EntityLink.link_type == link_type)
        ) |
        (
            (EntityLink.source_doc_id == target_doc_id) &
            (EntityLink.target_doc_id == source_doc_id) &
            (EntityLink.link_type == link_type)
        )
    ).first()
    if exists:
        return
    db.add(EntityLink(
        source_doc_id=source_doc_id,
        target_doc_id=target_doc_id,
        link_type=link_type,
        confidence=confidence,
        description=description
    ))

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
    
    # 1. Work item references: Jira-style keys, demo workflow IDs, and planning IDs.
    work_item_matches = JIRA_PATTERN.findall(text_content)
    for match in set(work_item_matches):
        work_item_id = match.upper()
        target_docs = db.query(Document).filter(
            Document.external_id == work_item_id,
            Document.id != doc.id
        ).all()
        for target in target_docs:
            create_entity_link(
                db,
                doc.id,
                target.id,
                "regex_match",
                1.0,
                f"Work item key '{work_item_id}' referenced in document text."
            )

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
            create_entity_link(
                db,
                doc.id,
                target.id,
                "regex_match",
                0.9,
                f"GitHub PR #{pr_id} referenced in document text."
            )

    # 3. URL references
    url_matches = {url.rstrip(".,") for url in URL_PATTERN.findall(text_content)}
    for url in url_matches:
        target_docs = db.query(Document).filter(
            Document.url == url,
            Document.id != doc.id
        ).all()
        for target in target_docs:
            create_entity_link(
                db,
                doc.id,
                target.id,
                "url_match",
                0.95,
                "A source URL was referenced directly in document text."
            )

    # 4. Branch references
    branch_matches = {branch.lower().rstrip(".,") for branch in BRANCH_PATTERN.findall(text_content)}
    for branch in branch_matches:
        target_docs = db.query(Document).filter(
            Document.body.like(f"%{branch}%"),
            Document.id != doc.id
        ).all()
        for target in target_docs:
            create_entity_link(
                db,
                doc.id,
                target.id,
                "branch_match",
                0.85,
                f"Branch '{branch}' appears in both related items."
            )

    db.commit()

def run_semantic_linking(db: Session, doc: Document, query_vector: list[float]):
    """Adds graph edges for close vector neighbors when deterministic links are absent."""
    try:
        results = search_similar_chunks(query_vector, limit=6)
    except Exception as e:
        print(f"Error semantic-linking document {doc.id}: {e}")
        return

    for chunk in results:
        target_doc_id = int(chunk.get("document_id", 0))
        if target_doc_id == doc.id:
            continue
        distance = float(chunk.get("_distance", 1.0))
        if distance > 0.85:
            continue
        target = db.query(Document).filter(Document.id == target_doc_id).first()
        if not target:
            continue
        create_entity_link(
            db,
            doc.id,
            target.id,
            "semantic_match",
            max(0.55, round(1.0 - distance, 2)),
            f"Semantic similarity linked this item to '{target.title}'."
        )
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
    first_vector = None
    if chunks:
        from app.embedder import get_embeddings
        try:
            embeddings = get_embeddings(chunks)
            if embeddings:
                first_vector = embeddings[0]
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
    if first_vector:
        run_semantic_linking(db, doc, first_vector)
    
    return doc

def build_fallback_context_card(
    doc: Document,
    linked_docs: list[dict],
    semantic_chunks: list[dict],
    llm_error: str = ""
) -> dict:
    """Builds a useful local card without requiring a hosted model."""
    intent = infer_intent(doc)
    evidence = [
        {
            "platform": item["platform"],
            "title": item["title"],
            "reason": item["link_reason"],
            "url": item.get("url")
        }
        for item in linked_docs[:5]
    ]
    evidence.extend([
        {
            "platform": item["platform"],
            "title": item["title"],
            "reason": "Semantic similarity",
            "url": item.get("url")
        }
        for item in semantic_chunks[:3]
    ])

    timeline = [
        {
            "timestamp": doc.created_at.isoformat() if doc.created_at else "",
            "label": f"{doc.platform.upper()} source item created",
            "detail": doc.title
        }
    ]
    for item in linked_docs[:4]:
        timeline.append({
            "timestamp": item.get("created_at", ""),
            "label": f"{item['platform'].upper()} related context",
            "detail": item["title"]
        })

    action_templates = {
        "bug_tracking": [
            {"label": "Open related source", "action_type": "open_url", "url": doc.url or "#"},
            {"label": "Draft ticket status update", "action_type": "draft_update", "payload": {"target": doc.external_id}},
            {"label": "Review linked PR or discussion", "action_type": "review_related"}
        ],
        "project_planning": [
            {"label": "Review missing owners", "action_type": "planning_review"},
            {"label": "Create follow-up task", "action_type": "draft_task"},
            {"label": "Open planning source", "action_type": "open_url", "url": doc.url or "#"}
        ],
        "personal_logistics": [
            {"label": "Confirm booking details", "action_type": "confirm_logistics"},
            {"label": "Create itinerary checklist", "action_type": "draft_checklist"},
            {"label": "Open original confirmation", "action_type": "open_url", "url": doc.url or "#"}
        ],
        "incident": [
            {"label": "Review incident timeline", "action_type": "incident_review"},
            {"label": "Draft stakeholder update", "action_type": "draft_update"},
            {"label": "Open source item", "action_type": "open_url", "url": doc.url or "#"}
        ]
    }

    linked_count = len(linked_docs)
    semantic_count = len(semantic_chunks)
    anomaly = ""
    if llm_error:
        anomaly = "Hosted/local LLM was unavailable, so StitchMind generated this card using local rules and retrieved evidence."
    elif linked_count == 0 and semantic_count == 0:
        anomaly = "No related evidence was found yet. Sync more sources or seed a demo workflow."

    return {
        "intent": intent,
        "summary": (
            f"{doc.title} is classified as {intent.replace('_', ' ')}. "
            f"StitchMind found {linked_count} deterministic links and {semantic_count} semantic matches, "
            "then assembled the strongest evidence into this local context card."
        ),
        "timeline": timeline,
        "evidence": evidence,
        "open_questions": [
            "Which linked item is the current source of truth?",
            "Is there a stale status or missing owner across the related platforms?"
        ],
        "risks": [
            "Related context may be incomplete until all relevant connectors are synced.",
            "Suggested actions are drafts and should be reviewed before posting externally."
        ],
        "anomalies": anomaly,
        "suggested_actions": action_templates.get(intent, [
            {"label": "Open original resource", "action_type": "open_url", "url": doc.url or "#"},
            {"label": "Review linked evidence", "action_type": "review_related"}
        ])
    }

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
                    "created_at": other_doc.created_at.isoformat() if other_doc.created_at else "",
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
        "  \"intent\": \"bug_tracking/project_planning/personal_logistics/incident/decision/general_context\",\n"
        "  \"summary\": \"Concise paragraph linking the conversations and documents together.\",\n"
        "  \"timeline\": [{\"timestamp\": \"ISO date if known\", \"label\": \"Short event\", \"detail\": \"What happened\"}],\n"
        "  \"evidence\": [{\"platform\": \"source platform\", \"title\": \"source title\", \"reason\": \"why it matters\", \"url\": \"link if available\"}],\n"
        "  \"open_questions\": [\"Important unresolved question\"],\n"
        "  \"risks\": [\"Risk, mismatch, or caveat\"],\n"
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
        parsed = json.loads(content)
        fallback = build_fallback_context_card(doc, linked_docs, semantic_chunks)
        return {**fallback, **parsed}
    except Exception as e:
        print(f"Error in LLM context unification completion: {e}")
        return build_fallback_context_card(doc, linked_docs, semantic_chunks, llm_error=str(e))
