"""
Retriever runtime untuk fondasi RAG figure One Piece.

Menerima query teks, meng-embed-nya memakai model yang sama dengan Ingestion,
lalu melakukan similarity search cosine di vector store dan mengembalikan top-K
Chunk terelevan. Mengembalikan struktur konsisten ``{"results": [...], "note"?}``
dan mengubah kesalahan embedder/vector store menjadi ``note`` sehingga MCP tool
pembungkus tetap tipis dan server tidak crash.
"""
from rag.embedder import embed_text, EmbedderError
from rag.vector_store import similarity_search, VectorStoreError

DEFAULT_TOP_K = 4
MIN_TOP_K = 1
MAX_TOP_K = 20


def _normalize_top_k(top_k) -> int:
    """Pastikan top_k berupa int positif pada rentang wajar; default bila tidak valid."""
    try:
        value = int(top_k)
    except (ValueError, TypeError):
        return DEFAULT_TOP_K
    if value < MIN_TOP_K:
        return DEFAULT_TOP_K
    return min(value, MAX_TOP_K)


def retrieve(query: str, top_k: int = DEFAULT_TOP_K) -> dict:
    """
    Cari Chunk pengetahuan paling relevan untuk sebuah query.

    Mengembalikan ``{"results": [{"content", "score", "document"}], "note"?}``.
    Query kosong/spasi menghasilkan note validasi tanpa memanggil embedder/DB;
    tabel kosong menghasilkan note "belum ada pengetahuan terindeks"; kegagalan
    embedder/vector store dipetakan menjadi note.
    """
    if query is None or not str(query).strip():
        return {"results": [], "note": "Query kosong. Masukkan teks pertanyaan."}

    k = _normalize_top_k(top_k)

    try:
        q_emb = embed_text(str(query))
        rows = similarity_search(q_emb, k)
    except (EmbedderError, VectorStoreError) as e:
        return {"results": [], "note": str(e)}

    if not rows:
        return {
            "results": [],
            "note": "Belum ada pengetahuan yang terindeks. Jalankan ingestion (python -m rag.ingest).",
        }

    results = [
        {"content": r["content"], "score": r["score"], "document": r["document"]}
        for r in rows
    ]
    return {"results": results}
