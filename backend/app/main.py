import datetime
import json
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel

from app.database import init_db, get_db, Connector, Document, EntityLink
from app.pipeline import process_and_index_document, unify_context
import app.config as config
from app.crypto import encrypt_value

app = FastAPI(
    title="StitchMind API", 
    description="AI Context Stitcher - Local Developer Portfolio App"
)

# CORS configuration to allow local React development server connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Safe for local execution
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup initialization
@app.on_event("startup")
def startup_event():
    init_db()
    # Try to initialize LanceDB connection
    try:
        from app.vector_store import get_chunks_table
        get_chunks_table()
        print("SQLite & LanceDB vector store initialized successfully.")
    except Exception as e:
        print(f"Startup warning: Vector store failed to initialize. {e}")

# Pydantic Request/Response DTOs
class ConnectorCreate(BaseModel):
    platform: str
    name: str
    auth_config: dict
    sync_interval_mins: Optional[int] = 15

class ConnectorResponse(BaseModel):
    id: int
    platform: str
    name: str
    is_active: bool
    last_sync: Optional[datetime.datetime] = None
    sync_interval_mins: int

    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: int
    platform: str
    external_id: str
    title: str
    body: str
    url: Optional[str] = None
    author: Optional[str] = None
    created_at: datetime.datetime
    synced_at: datetime.datetime

    class Config:
        from_attributes = True

class ConfigUpdate(BaseModel):
    gemini_api_key: Optional[str] = None
    ollama_host: Optional[str] = None

# --- Core API Endpoints ---

@app.get("/api/health")
def health_check():
    return {
        "status": "ok", 
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "database": "connected"
    }

# --- Config Management ---

@app.get("/api/config")
def get_app_config():
    return {
        "gemini_api_key_configured": bool(config.GEMINI_API_KEY),
        "ollama_host": config.OLLAMA_HOST,
        "embedding_model": config.EMBEDDING_MODEL_NAME
    }

@app.post("/api/config")
def update_app_config(payload: ConfigUpdate):
    if payload.gemini_api_key is not None:
        config.GEMINI_API_KEY = payload.gemini_api_key
        # Optionally save to a local env or config cache
    if payload.ollama_host is not None:
        config.OLLAMA_HOST = payload.ollama_host
    return {"status": "success", "config": get_app_config()}

# --- Connector Management ---

@app.get("/api/connectors", response_model=List[ConnectorResponse])
def get_connectors(db: Session = Depends(get_db)):
    return db.query(Connector).all()

@app.post("/api/connectors", response_model=ConnectorResponse)
def create_connector(payload: ConnectorCreate, db: Session = Depends(get_db)):
    connector = Connector(
        platform=payload.platform,
        name=payload.name,
        sync_interval_mins=payload.sync_interval_mins
    )
    connector.set_auth_config(payload.auth_config)
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector

@app.delete("/api/connectors/{connector_id}")
def delete_connector(connector_id: int, db: Session = Depends(get_db)):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    db.delete(connector)
    db.commit()
    return {"status": "success", "message": f"Connector {connector_id} deleted"}

# --- Document Management ---

@app.get("/api/documents", response_model=List[DocumentResponse])
def get_documents(
    platform: Optional[str] = None, 
    search: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    query = db.query(Document)
    if platform:
        query = query.filter(Document.platform == platform)
    if search:
        query = query.filter(
            Document.title.like(f"%{search}%") | Document.body.like(f"%{search}%")
        )
    return query.order_by(Document.synced_at.desc()).all()

@app.get("/api/documents/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

# --- Context Stitching & LLM ---

@app.get("/api/documents/{doc_id}/stitch")
def stitch_document_context(
    doc_id: int, 
    use_local_llm: bool = False, 
    local_model: str = "llama3", 
    db: Session = Depends(get_db)
):
    result = unify_context(db, doc_id, use_local_llm=use_local_llm, local_model=local_model)
    return result

# --- Entity Links (Graph visualization) ---

@app.get("/api/links")
def get_entity_links(db: Session = Depends(get_db)):
    links = db.query(EntityLink).all()
    results = []
    for link in links:
        source = db.query(Document).filter(Document.id == link.source_doc_id).first()
        target = db.query(Document).filter(Document.id == link.target_doc_id).first()
        if source and target:
            results.append({
                "id": link.id,
                "source": {
                    "id": source.id,
                    "title": source.title,
                    "platform": source.platform
                },
                "target": {
                    "id": target.id,
                    "title": target.title,
                    "platform": target.platform
                },
                "link_type": link.link_type,
                "confidence": link.confidence,
                "description": link.description
            })
    return results

# --- Mock Seeding for Portfolio Demos ---

@app.post("/api/seed-mock-data")
def seed_mock_data(db: Session = Depends(get_db)):
    """Seeds relational SQLite and LanceDB with realistic cross-platform items to demonstrate mapping."""
    try:
        # Create a mock connector first
        connector = db.query(Connector).filter(Connector.platform == "mock").first()
        if not connector:
            connector = Connector(platform="mock", name="Demo Playground Connector")
            connector.set_auth_config({"demo": "enabled"})
            db.add(connector)
            db.commit()
            db.refresh(connector)

        # 1. Jira Ticket Doc
        jira_doc = process_and_index_document(
            db=db,
            connector_id=connector.id,
            external_id="PROJ-101",
            platform="jira",
            title="PROJ-101: Fix OAuth Session Token Refresh Loop",
            body=(
                "Severity: High. Users logging in via mobile devices experience a cyclic loop "
                "where refresh tokens expire immediately after issuance. Expected behavior: "
                "JWT session refresh should persist token validity for 7 days. "
                "Needs revision on JWT payload validation timestamps."
            ),
            url="https://jira.company.com/browse/PROJ-101",
            author="Alice ProductManager",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
        )

        # 2. Slack Message Doc (referencing Jira Ticket)
        slack_doc = process_and_index_document(
            db=db,
            connector_id=connector.id,
            external_id="slack_msg_10923",
            platform="slack",
            title="Slack Thread in #engineering-auth",
            body=(
                "Bob: Hey guys, I am looking into PROJ-101. It looks like the server's time validation "
                "discrepancy (UTC vs local clock skew) is causing the JWT to look expired immediately. "
                "I am pushing a fix to branch oauth-skew-fix and creating a PR."
            ),
            url="https://slack.company.com/archives/C12345/p10923",
            author="Bob Developer",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )

        # 3. GitHub PR Doc (referencing Jira Ticket and Slack code terms)
        github_doc = process_and_index_document(
            db=db,
            connector_id=connector.id,
            external_id="202",
            platform="github",
            title="PR #202: Fix token expiration clock skew error (PROJ-101)",
            body=(
                "This PR resolves the JWT expiration token issues described in PROJ-101. "
                "Added a clock skew leeway of 60 seconds inside jwt_verifier.py. "
                "Co-authored by Alice PM. Resolves regression bugs identified in auth backend."
            ),
            url="https://github.com/company/stitchmind/pull/202",
            author="Bob Developer",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=12)
        )

        # 4. Google Doc (representing architecture blueprint)
        gdoc_doc = process_and_index_document(
            db=db,
            connector_id=connector.id,
            external_id="gdoc_spec_987",
            platform="google_workspace",  # Treated as Google Docs
            title="StitchMind Token Validation Architecture",
            body=(
                "System Architecture for Auth Session Management. We utilize JWTs with HS256 algorithm. "
                "Token refresh occurs automatically on API requests when expiration is within 5 minutes. "
                "Any clock skew between API gateway and client auth server must be accounted for "
                "specifically in jwt_verifier.py to prevent loops."
            ),
            url="https://docs.google.com/document/d/987_oauth_spec",
            author="System Architect",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=5)
        )

        return {
            "status": "success", 
            "message": "Seeded mock project data successfully. Linked Jira PROJ-101, Slack thread, GitHub PR #202, and Google Doc via regex and semantic layers."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to seed demo data: {str(e)}")
