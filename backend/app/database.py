import datetime
import json
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from app.config import DATABASE_URL
from app.crypto import encrypt_value, decrypt_value

# Create SQLite engine
# check_same_thread=False is safe because SQLite is used in a local app, but we must handle thread isolation
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Connector(Base):
    __tablename__ = "connectors"
    
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, index=True)  # e.g., 'github', 'slack', 'jira', 'google_workspace'
    name = Column(String)
    encrypted_auth_config = Column(Text)  # JSON credentials string (encrypted)
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime, nullable=True)
    sync_interval_mins = Column(Integer, default=15)
    
    documents = relationship("Document", back_populates="connector", cascade="all, delete-orphan")
    
    def set_auth_config(self, config_dict: dict):
        raw_json = json.dumps(config_dict)
        self.encrypted_auth_config = encrypt_value(raw_json)
        
    def get_auth_config(self) -> dict:
        if not self.encrypted_auth_config:
            return {}
        decrypted = decrypt_value(self.encrypted_auth_config)
        return json.loads(decrypted)

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    connector_id = Column(Integer, ForeignKey("connectors.id"), nullable=True)
    external_id = Column(String, index=True)  # Platform specific ID
    title = Column(String)
    body = Column(Text)
    url = Column(String, nullable=True)
    author = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    connector = relationship("Connector", back_populates="documents")

class EntityLink(Base):
    __tablename__ = "entity_links"
    
    id = Column(Integer, primary_key=True, index=True)
    source_doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    target_doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    link_type = Column(String)  # regex_match, llm_inferred, manual
    confidence = Column(Float, default=1.0)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # We define separate foreign key relations for source and target
    source_document = relationship("Document", foreign_keys=[source_doc_id])
    target_document = relationship("Document", foreign_keys=[target_doc_id])

def init_db():
    """Initializes tables on startup if they don't exist."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
