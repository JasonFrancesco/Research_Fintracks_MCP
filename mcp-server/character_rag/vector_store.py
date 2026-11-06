"""
=============================================================================
 CHARACTER RAG — VECTOR STORE (pgvector)
=============================================================================
Konfigurasi vector store berbasis PostgreSQL + ekstensi pgvector, menggantikan
penyimpanan file JSON (LlamaIndex SimpleVectorStore) yang lama.

Vektor embedding (1024-dim BAAI/bge-m3) disimpan di tabel PostgreSQL. Pencarian
kemiripan (cosine) dilakukan langsung di database melalui pgvector, bukan lagi
in-memory dari file JSON.

Dipakai oleh:
- ingest.py   : menulis vektor ke tabel saat indexing.
- retriever.py: membaca/mencari vektor saat runtime (dense retrieval).

Konfigurasi koneksi dibaca dari DATABASE_URL (.env mcp-server atau backend).
Nama tabel: data_onepiece_characters (LlamaIndex menambah prefix 'data_').
=============================================================================
"""
import os
import re
from pathlib import Path
from urllib.parse import urlparse, unquote

from llama_index.vector_stores.postgres import PGVectorStore

# Nama tabel vektor (tanpa prefix 'data_' yang otomatis ditambah LlamaIndex).
TABLE_NAME = "onepiece_characters"
EMBED_DIM = 1024  # dimensi vektor BAAI/bge-m3


def _load_db_url() -> str:
    """Baca DATABASE_URL dari .env (mcp-server diutamakan, lalu backend)."""
    from dotenv import load_dotenv
    here = Path(__file__).resolve().parent.parent          # mcp-server/
    load_dotenv(here / ".env")
    load_dotenv(here.parent / "backend" / ".env")
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL tidak ditemukan di .env. Pastikan PostgreSQL dikonfigurasi."
        )
    return url


def get_pg_vector_store(perform_setup: bool = False) -> PGVectorStore:
    """
    Buat instance PGVectorStore dari DATABASE_URL.

    perform_setup=True hanya dipakai saat ingestion (membuat tabel + ekstensi).
    Saat runtime (retrieval), perform_setup=False agar tidak mencoba membuat ulang.
    """
    url = _load_db_url()
    p = urlparse(url)

    return PGVectorStore.from_params(
        host=p.hostname or "localhost",
        port=str(p.port or 5432),
        database=(p.path or "/fintracks").lstrip("/"),
        user=unquote(p.username or "postgres"),
        password=unquote(p.password or ""),
        table_name=TABLE_NAME,
        embed_dim=EMBED_DIM,
        perform_setup=perform_setup,
        hybrid_search=False,            # hybrid lexical ditangani sendiri di retriever.py
    )


def ensure_vector_extension() -> None:
    """Pastikan ekstensi pgvector aktif di database (idempoten)."""
    import psycopg2
    url = _load_db_url()
    conn = psycopg2.connect(url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    finally:
        conn.close()
