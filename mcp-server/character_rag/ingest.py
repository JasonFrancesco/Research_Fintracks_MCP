"""
=============================================================================
 CHARACTER RAG — INGESTION (ingest.py)
=============================================================================
Script OFFLINE idempoten yang membangun Persisted_Index pengetahuan karakter
One Piece memakai LlamaIndex + embedding lokal ``all-MiniLM-L6-v2``.

Alur: CSV -> adapter.load_characters() -> build_document() (teks naratif +
metadata) -> HuggingFaceEmbedding (Settings.embed_model) ->
VectorStoreIndex.from_documents() -> storage_context.persist(STORAGE_DIR).

Jalankan dari direktori ``mcp-server`` dengan:

    python -m character_rag.ingest

Menjalankan ingestion mengunduh model ``all-MiniLM-L6-v2`` sekali dari HF Hub
lalu meng-cache-nya lokal (bisa LAMA pada run pertama).
=============================================================================
"""
import sys
from pathlib import Path

# Sisipkan server_dir (= mcp-server/) ke sys.path agar impor
# `from character_rag.adapter import ...` bekerja sama seperti modul lain.
server_dir = str(Path(__file__).resolve().parent.parent)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from llama_index.core import VectorStoreIndex, Settings, Document
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from character_rag.adapter import load_characters, CharacterAdapterError

STORAGE_DIR = Path(__file__).resolve().parent / "storage"
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def build_document(record: dict) -> Document:
    """
    Ubah satu record karakter menjadi satu Document naratif + metadata {id, nama}.

    Kalimat naratif (bahasa alami) membuat embedding lebih mewakili makna
    karakter dibanding baris CSV mentah, sehingga semantic search lebih akurat.
    """
    nama = record["Nama"]
    julukan = record["Julukan"]
    afil = record["Afiliasi"]
    peran = record["Peran"]
    bounty = record["Bounty (Beli)"]
    buah = record["Buah Iblis"]
    tipe = record["Tipe Buah Iblis"]

    text = (
        f"{nama}, dijuluki {julukan}, adalah {peran} dari {afil}. "
        f"Bounty-nya {bounty} Berry. "
        f"Buah iblis: {buah}"
        + (f" (tipe {tipe})." if tipe and tipe != "-" else ".")
    )
    return Document(text=text, metadata={"id": record["ID"], "nama": nama})


def main() -> None:
    # Set embedder GLOBAL — harus identik dengan retriever (invariant kebenaran).
    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)

    try:
        records = load_characters()
    except CharacterAdapterError as e:
        print(f"Ingestion dibatalkan: {e}")
        return
    if not records:
        print("Tidak ada karakter untuk diindeks.")
        return

    documents = [build_document(r) for r in records]
    index = VectorStoreIndex.from_documents(documents)
    index.storage_context.persist(persist_dir=str(STORAGE_DIR))

    print(f"Selesai. {len(documents)} dokumen karakter diindeks.")
    print(f"Persisted_Index disimpan di: {STORAGE_DIR}")


if __name__ == "__main__":
    main()
