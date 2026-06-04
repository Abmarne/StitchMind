import numpy as np
from app.config import EMBEDDING_MODEL_NAME

# Global model cache to avoid reloading
_model = None

def get_embedding_model():
    """Lazily loads and returns the SentenceTransformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Downloads the ~90MB model automatically on first run and caches it
            _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        except Exception as e:
            print(f"Error loading local SentenceTransformer ({EMBEDDING_MODEL_NAME}): {e}")
            raise e
    return _model

def get_embedding(text: str) -> list[float]:
    """Generates a 384-dimension vector embedding for a single text string."""
    model = get_embedding_model()
    embedding = model.encode(text)
    if isinstance(embedding, np.ndarray):
        return embedding.tolist()
    return [float(x) for x in embedding]

def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Generates a list of embeddings for multiple text strings in a batch."""
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(texts)
    if isinstance(embeddings, np.ndarray):
        return embeddings.tolist()
    return [[float(x) for x in emb] for emb in embeddings]
