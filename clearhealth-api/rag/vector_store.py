"""
ChromaDB vector store wrapper for CBT-i document retrieval.
"""
import chromadb
from pathlib import Path

_client = None
_collection = None

COLLECTION_NAME = "cbti_docs"
CHROMA_PATH = Path(__file__).parent / ".chroma"


def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_documents(documents: list[str], ids: list[str], metadatas: list[dict] | None = None):
    """Add text chunks to the vector store."""
    col = get_collection()
    col.add(documents=documents, ids=ids, metadatas=metadatas or [{} for _ in documents])


def query(text: str, n_results: int = 3) -> list[str]:
    """Return top-n relevant CBT-i text chunks for a query."""
    col = get_collection()
    if col.count() == 0:
        return []
    results = col.query(query_texts=[text], n_results=min(n_results, col.count()))
    return results["documents"][0] if results["documents"] else []


def is_empty() -> bool:
    return get_collection().count() == 0
