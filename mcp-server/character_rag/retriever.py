"""
=============================================================================
 CHARACTER RAG — RETRIEVAL (retriever.py)
=============================================================================
Retrieval runtime untuk pengetahuan karakter One Piece. Memuat Persisted_Index
hasil ingestion, meng-embed query memakai model embedding yang SAMA, lalu
melakukan semantic search top-K dan mengembalikan konteks + metadata.

Mengikuti kontrak ``retrieve(query, top_k) -> dict`` seperti rag/retriever.py:
mengembalikan ``{"results": [...], "note"?}`` dan mengubah kondisi non-ideal
(query kosong, index belum dibangun, kegagalan muat) menjadi ``note`` agar MCP
wrapper tetap tipis dan server tidak crash.
=============================================================================
"""
from pathlib import Path

from llama_index.core import StorageContext, load_index_from_storage, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

STORAGE_DIR = Path(__file__).resolve().parent / "storage"
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_TOP_K = 4
MIN_TOP_K = 1
MAX_TOP_K = 20

_index = None  # cache proses: hindari reload index/embedder tiap panggilan


def _normalize_top_k(top_k) -> int:
    """Pastikan top_k int pada rentang [MIN_TOP_K, MAX_TOP_K]; default bila tidak valid."""
    try:
        value = int(top_k)
    except (ValueError, TypeError):
        return DEFAULT_TOP_K
    if value < MIN_TOP_K:
        return DEFAULT_TOP_K
    return min(value, MAX_TOP_K)


def _load_index():
    """Muat Persisted_Index sekali lalu cache. Embedder identik dengan ingestion."""
    global _index
    if _index is None:
        Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)
        ctx = StorageContext.from_defaults(persist_dir=str(STORAGE_DIR))
        _index = load_index_from_storage(ctx)
    return _index


def retrieve(query: str, top_k: int = DEFAULT_TOP_K) -> dict:
    """
    Cari karakter paling relevan secara semantik untuk sebuah query.

    Mengembalikan ``{"results": [{"text", "id", "nama", "score"}], "note"?}``.
    Query kosong/spasi -> note validasi tanpa memuat index/embedder.
    Index belum dibangun -> note dengan petunjuk menjalankan ingestion.
    Kegagalan muat/retrieval -> note.
    """
    if query is None or not str(query).strip():
        return {"results": [], "note": "Query kosong. Masukkan teks pertanyaan."}

    if not STORAGE_DIR.exists():
        return {
            "results": [],
            "note": "Indeks karakter belum dibangun. Jalankan: python -m character_rag.ingest",
        }

    k = _normalize_top_k(top_k)

    try:
        index = _load_index()
        nodes = index.as_retriever(similarity_top_k=k).retrieve(str(query))
    except Exception as e:
        return {"results": [], "note": f"Gagal melakukan retrieval karakter: {e}"}

    results = [
        {
            "text": n.node.get_content(),
            "id": n.node.metadata.get("id"),
            "nama": n.node.metadata.get("nama"),
            "score": float(n.score) if n.score is not None else None,
        }
        for n in nodes
    ]
    return {"results": results}
