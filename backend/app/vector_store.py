import lancedb
import pyarrow as pa
from app.config import LANCE_DB_PATH

# Global connection placeholder
db_conn = None

def get_vector_db():
    """Returns the singleton LanceDB connection."""
    global db_conn
    if db_conn is None:
        db_conn = lancedb.connect(LANCE_DB_PATH)
    return db_conn

def get_chunks_table():
    """Returns or creates the 'chunks' table with PyArrow schema validation."""
    db = get_vector_db()
    
    # Define a 384-dimension vector schema (matching all-MiniLM-L6-v2)
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("document_id", pa.int32()),
        pa.field("chunk_index", pa.int32()),
        pa.field("text", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 384)),
        pa.field("platform", pa.string()),
        pa.field("url", pa.string()),
        pa.field("title", pa.string())
    ])
    
    if "chunks" in db.table_names():
        return db.open_table("chunks")
    else:
        return db.create_table("chunks", schema=schema)

def add_chunks(chunks_list: list[dict]):
    """Adds a list of chunks into LanceDB."""
    if not chunks_list:
        return
    table = get_chunks_table()
    table.add(chunks_list)

def delete_chunks_by_document(document_id: int):
    """Cleans up any existing vector chunks of a specific document (e.g., prior to re-indexing)."""
    table = get_chunks_table()
    table.delete(f"document_id = {document_id}")

def search_similar_chunks(query_vector: list[float], limit: int = 5, platform: str = None) -> list[dict]:
    """Queries LanceDB for top-K nearest neighbors based on the query embedding."""
    table = get_chunks_table()
    
    # Build query
    query = table.search(query_vector)
    
    if platform:
        query = query.where(f"platform = '{platform}'")
        
    results = query.limit(limit).to_list()
    return results
