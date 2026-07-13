"""Jarvis Core — shared production prompt/context builder.

Extracted from main.py's ask_llm() so BOTH production and the eval engine
build the exact same system prompt + RAG context. Without this, the eval
engine tests "can the bare model answer questions," not "can the actual
Keshri Pipes bot answer questions" — those are very different tests, and
the difference is invisible until you see a 100% fail rate that turns out
to be a missing system prompt, not a bad model.

TODO (flagged, not done yet): main.py's ask_llm() still has this logic
inline rather than importing from here. Until that's changed, there are
two copies of the same logic that could drift apart. Low risk right now
since this file was copied verbatim from the current main.py, but worth
fixing next time main.py's persona changes.
"""

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

EMBED_MODEL = "all-MiniLM-L6-v2"
CHROMA_DIR = "chroma_db"
CHROMA_COLLECTION = "kb_keshri_pipes"

_catalog = None  # lazy init, same collection main.py connects to


def _get_catalog():
    global _catalog
    if _catalog is None:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _catalog = client.get_collection(
            name=CHROMA_COLLECTION,
            embedding_function=SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL),
        )
    return _catalog


def get_catalog_context(user_text: str, n_results: int = 4) -> str:
    """Same RAG retrieval main.py's ask_llm() does. Returns empty string
    (not an exception) if Chroma/the collection isn't reachable, so eval
    runs on a machine without the catalog ingested still produce SOME
    signal rather than crashing — tier1's expected_keywords checks will
    just fail honestly instead."""
    try:
        catalog = _get_catalog()
        retrieved = catalog.query(query_texts=[user_text], n_results=n_results)
        return "\n".join(retrieved["documents"][0])
    except Exception:
        return ""


def build_system_prompt(user_text: str) -> str:
    """Verbatim from main.py's ask_llm(), parameterized by the retrieved
    catalog context for this specific user_text."""
    catalog_context = get_catalog_context(user_text)
    return (
        "You are the assistant for Keshri Pipes, a wholesale pipe fitting "
        "supplier. Be brief, warm, and professional. Hindi-English mix is "
        "fine if the customer uses it.\n\n"
        "Answer ONLY using the catalog information below. If the answer is "
        "not in the catalog, say you'll check with the team — never invent "
        "products, prices, or stock.\n\n"
        f"CATALOG:\n{catalog_context}"
    )
