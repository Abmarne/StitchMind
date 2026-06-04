import datetime
import json
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel

from app.database import init_db, get_db, Connector, Document, EntityLink
from app.pipeline import process_and_index_document, unify_context
from app.vector_store import reset_vector_store
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

class WebhookPayload(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    external_id: Optional[str] = None
    url: Optional[str] = None
    author: Optional[str] = None
    raw: Optional[Dict] = None

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

@app.post("/api/connectors/{connector_id}/sync")
def sync_connector(connector_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    connector.last_sync = datetime.datetime.utcnow()
    db.commit()
    return {
        "status": "queued",
        "message": (
            f"{connector.platform} sync hook accepted. Real polling connectors can attach here; "
            "the zero-cost demo uses seeded and webhook-ingested documents."
        )
    }

@app.post("/api/webhooks/{platform}")
def receive_webhook(platform: str, payload: WebhookPayload, db: Session = Depends(get_db)):
    connector = db.query(Connector).filter(Connector.platform == platform).first()
    if not connector:
        connector = Connector(platform=platform, name=f"{platform.title()} Webhook Connector")
        connector.set_auth_config({"mode": "webhook_demo"})
        db.add(connector)
        db.commit()
        db.refresh(connector)

    raw = payload.raw or {}
    title = payload.title or raw.get("title") or raw.get("subject") or f"{platform.title()} webhook event"
    body = payload.body or raw.get("body") or raw.get("text") or json.dumps(raw)
    external_id = payload.external_id or raw.get("id") or f"webhook-{int(datetime.datetime.utcnow().timestamp())}"

    doc = process_and_index_document(
        db=db,
        connector_id=connector.id,
        external_id=str(external_id),
        platform=platform,
        title=title,
        body=body,
        url=payload.url or raw.get("url"),
        author=payload.author or raw.get("author"),
        created_at=datetime.datetime.utcnow()
    )
    return {"status": "indexed", "document_id": doc.id}

@app.delete("/api/privacy/local-data")
def delete_local_data(db: Session = Depends(get_db)):
    db.query(EntityLink).delete()
    db.query(Document).delete()
    db.query(Connector).delete()
    db.commit()
    reset_vector_store()
    return {"status": "success", "message": "Deleted local documents, links, connectors, and vector chunks."}

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
    """Seeds relational SQLite and LanceDB with realistic cross-platform workflows."""
    try:
        connector = db.query(Connector).filter(Connector.platform == "mock").first()
        if not connector:
            connector = Connector(platform="mock", name="Demo Workflow Sandbox")
            connector.set_auth_config({"demo": "enabled"})
            db.add(connector)
            db.commit()
            db.refresh(connector)

        now = datetime.datetime.utcnow()
        demo_docs = [
            {
                "external_id": "PROJ-101",
                "platform": "jira",
                "title": "PROJ-101: Fix OAuth Session Token Refresh Loop",
                "body": (
                    "Severity: High. Users logging in via mobile devices experience a cyclic loop where refresh "
                    "tokens expire immediately after issuance. Expected behavior: JWT session refresh should "
                    "persist token validity for 7 days. Needs revision on JWT payload validation timestamps."
                ),
                "url": "https://jira.company.com/browse/PROJ-101",
                "author": "Alice ProductManager",
                "created_at": now - datetime.timedelta(days=2)
            },
            {
                "external_id": "slack_msg_10923",
                "platform": "slack",
                "title": "Slack Thread in #engineering-auth",
                "body": (
                    "Bob: I am looking into PROJ-101. UTC vs local clock skew is causing the JWT to look expired "
                    "immediately. I am pushing branch oauth-skew-fix and creating PR #202."
                ),
                "url": "https://slack.company.com/archives/C12345/p10923",
                "author": "Bob Developer",
                "created_at": now - datetime.timedelta(days=1)
            },
            {
                "external_id": "202",
                "platform": "github",
                "title": "PR #202: Fix token expiration clock skew error (PROJ-101)",
                "body": (
                    "This PR resolves PROJ-101 from branch oauth-skew-fix. Added a clock skew leeway of 60 seconds "
                    "inside jwt_verifier.py. Resolves regression bugs identified in auth backend."
                ),
                "url": "https://github.com/company/stitchmind/pull/202",
                "author": "Bob Developer",
                "created_at": now - datetime.timedelta(hours=12)
            },
            {
                "external_id": "gdoc_spec_987",
                "platform": "google_workspace",
                "title": "StitchMind Token Validation Architecture",
                "body": (
                    "System Architecture for Auth Session Management. PROJ-101 must account for clock skew between "
                    "API gateway and client auth server inside jwt_verifier.py to prevent refresh loops."
                ),
                "url": "https://docs.google.com/document/d/987_oauth_spec",
                "author": "System Architect",
                "created_at": now - datetime.timedelta(days=5)
            },
            {
                "external_id": "PLAN-42",
                "platform": "jira",
                "title": "PLAN-42: Q3 Launch Readiness Epic",
                "body": (
                    "Epic for Q3 launch readiness. Scope includes billing migration, onboarding copy, analytics QA, "
                    "and launch checklist ownership. Status is at risk until analytics owner is assigned."
                ),
                "url": "https://jira.company.com/browse/PLAN-42",
                "author": "Mira ProgramLead",
                "created_at": now - datetime.timedelta(days=8)
            },
            {
                "external_id": "gdoc_plan_q3",
                "platform": "google_workspace",
                "title": "Q3 Launch Plan And Dependencies",
                "body": (
                    "PLAN-42 depends on final pricing copy, QA sign-off, and milestone tracking. The planning doc "
                    "recommends a launch freeze by Friday and review of GitHub milestone PR #88."
                ),
                "url": "https://docs.google.com/document/d/q3_launch_plan",
                "author": "Mira ProgramLead",
                "created_at": now - datetime.timedelta(days=6)
            },
            {
                "external_id": "gmail_plan_thread",
                "platform": "gmail",
                "title": "Email: Launch owners and analytics gap",
                "body": (
                    "Subject: PLAN-42 launch owners. The analytics dashboard still lacks an owner. Please review "
                    "the Q3 Launch Plan and PR #88 before the readiness meeting."
                ),
                "url": "https://mail.google.com/mail/u/0/#inbox/plan42",
                "author": "ops@example.com",
                "created_at": now - datetime.timedelta(days=3)
            },
            {
                "external_id": "88",
                "platform": "github",
                "title": "PR #88: Add launch analytics milestone dashboard",
                "body": (
                    "Implements launch analytics dashboard for PLAN-42. Remaining TODO: assign dashboard owner and "
                    "confirm event naming before Q3 launch freeze."
                ),
                "url": "https://github.com/company/stitchmind/pull/88",
                "author": "Nikhil Engineer",
                "created_at": now - datetime.timedelta(days=2)
            },
            {
                "external_id": "TRIP-2026",
                "platform": "google_workspace",
                "title": "TRIP-2026: Tokyo Itinerary",
                "body": (
                    "Personal trip plan for Tokyo. Arrive June 18, hotel check-in after 3 PM, museum booking on "
                    "June 20, and airport transfer still needs confirmation."
                ),
                "url": "https://docs.google.com/document/d/tokyo_trip_2026",
                "author": "Abhiraj",
                "created_at": now - datetime.timedelta(days=10)
            },
            {
                "external_id": "gmail_flight_tokyo",
                "platform": "gmail",
                "title": "Flight confirmation for Tokyo",
                "body": (
                    "Booking confirmation for TRIP-2026. Flight AI-306 departs June 18 at 01:15 and arrives Tokyo "
                    "at 13:40. Check passport validity and baggage allowance."
                ),
                "url": "https://mail.google.com/mail/u/0/#inbox/trip-flight",
                "author": "airline@example.com",
                "created_at": now - datetime.timedelta(days=9)
            },
            {
                "external_id": "gmail_hotel_tokyo",
                "platform": "gmail",
                "title": "Hotel check-in instructions",
                "body": (
                    "Hotel confirmation for TRIP-2026. Check-in starts at 3 PM, address is near Shinjuku Station, "
                    "and the airport transfer is not included."
                ),
                "url": "https://mail.google.com/mail/u/0/#inbox/trip-hotel",
                "author": "hotel@example.com",
                "created_at": now - datetime.timedelta(days=7)
            },
            {
                "external_id": "slack_trip_notes",
                "platform": "slack",
                "title": "Chat notes: Tokyo museum and transfer",
                "body": (
                    "Reminder for TRIP-2026: book museum tickets for June 20 and confirm whether airport transfer "
                    "is needed after hotel check-in instructions."
                ),
                "url": "https://slack.example.com/archives/personal/trip",
                "author": "Travel Buddy",
                "created_at": now - datetime.timedelta(days=4)
            }
        ]

        for item in demo_docs:
            process_and_index_document(db=db, connector_id=connector.id, **item)

        return {
            "status": "success", 
            "message": (
                "Seeded developer bug, project planning, and personal trip workflows. "
                "Documents are linked through work-item keys, PR references, URLs, branch mentions, and semantic similarity."
            )
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to seed demo data: {str(e)}")
