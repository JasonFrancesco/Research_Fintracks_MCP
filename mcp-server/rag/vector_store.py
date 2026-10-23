"""
Vector store pgvector untuk fondasi RAG figure One Piece.

Menyimpan dan mencari Chunk pengetahuan di PostgreSQL database ``fintracks`` yang
sudah ada, memakai koneksi/``DATABASE_URL`` dari ``mcp-server/config.py``. Semua
operasi SQL ditulis mentah via ``sqlalchemy.text()`` dengan cast ``::vector``,
mengikuti pola sesi tools existing (``db = get_db_session(); try/finally: close``).
"""
import sys
from pathlib import Path

# Sisipkan direktori mcp-server/ ke sys.path agar `from config import ...`
# konsisten dengan pola tools/transaction_tools.py.
server_dir = str(Path(__file__).resolve().parent.parent)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from config import get_db_session


class VectorStoreError(Exception):
    """Kesalahan yang dapat dijelaskan ke pengguna saat operasi vector store gagal."""


def _vec_literal(embedding: list[float]) -> str:
    """Format list float menjadi string literal pgvector ``'[v1,v2,...]'``."""
    return "[" + ",".join(repr(float(v)) for v in embedding) + "]"


def ensure_extension_and_table() -> None:
    """
    Pastikan ekstensi pgvector aktif dan tabel ``figure_knowledge_chunks`` ada.

    Menjalankan ``CREATE EXTENSION IF NOT EXISTS vector`` lalu DDL tabel. Bila
    ekstensi belum terpasang di server PostgreSQL, melempar ``VectorStoreError``
    dengan petunjuk pemasangan.
    """
    db = get_db_session()
    try:
        try:
            db.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        except (ProgrammingError, OperationalError) as e:
            db.rollback()
            msg = str(e).lower()
            if (
                "could not open extension control file" in msg
                or 'extension "vector" is not available' in msg
                or "is not available" in msg
            ):
                raise VectorStoreError(
                    "Ekstensi pgvector belum terpasang di server PostgreSQL. "
                    "Pasang pgvector untuk PostgreSQL terlebih dahulu sebelum "
                    "fitur RAG dapat dipakai."
                ) from e
            raise

        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS figure_knowledge_chunks (
                    id          SERIAL PRIMARY KEY,
                    document    TEXT        NOT NULL,
                    chunk_index INTEGER     NOT NULL,
                    content     TEXT        NOT NULL,
                    embedding   vector(768) NOT NULL,
                    created_at  TIMESTAMP   NOT NULL DEFAULT now(),
                    CONSTRAINT uq_figure_chunk UNIQUE (document, chunk_index)
                );
                """
            )
        )
        db.commit()
    finally:
        db.close()


def upsert_chunk(document: str, chunk_index: int, content: str, embedding: list[float]) -> None:
    """
    Sisipkan atau perbarui satu Chunk berdasarkan kunci unik (document, chunk_index).

    Embedding di-bind sebagai string literal (via ``_vec_literal``) lalu di-cast
    ``CAST(:embedding AS vector)`` — nilai lewat parameter bind, bukan interpolasi
    string, agar aman dari injeksi.
    """
    db = get_db_session()
    try:
        db.execute(
            text(
                """
                INSERT INTO figure_knowledge_chunks (document, chunk_index, content, embedding)
                VALUES (:document, :chunk_index, :content, CAST(:embedding AS vector))
                ON CONFLICT (document, chunk_index)
                DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding;
                """
            ),
            {
                "document": document,
                "chunk_index": chunk_index,
                "content": content,
                "embedding": _vec_literal(embedding),
            },
        )
        db.commit()
    finally:
        db.close()


def delete_document_chunks(document: str) -> int:
    """Hapus semua Chunk milik sebuah dokumen; kembalikan jumlah baris terhapus."""
    db = get_db_session()
    try:
        result = db.execute(
            text("DELETE FROM figure_knowledge_chunks WHERE document = :document;"),
            {"document": document},
        )
        db.commit()
        return result.rowcount
    finally:
        db.close()


def similarity_search(query_embedding: list[float], top_k: int) -> list[dict]:
    """
    Cari Chunk paling mirip dengan embedding query (cosine similarity).

    Memakai operator cosine distance ``<=>`` pgvector; ``score = 1 - distance``
    sehingga nilai mendekati 1 berarti sangat mirip. Mengembalikan daftar
    ``{"document", "content", "score"}`` terurut skor tertinggi lebih dulu.
    """
    db = get_db_session()
    try:
        rows = db.execute(
            text(
                """
                SELECT document, content,
                       1 - (embedding <=> CAST(:query AS vector)) AS score
                FROM figure_knowledge_chunks
                ORDER BY embedding <=> CAST(:query AS vector)
                LIMIT :top_k;
                """
            ),
            {"query": _vec_literal(query_embedding), "top_k": top_k},
        ).fetchall()
        return [
            {"document": r[0], "content": r[1], "score": float(r[2])}
            for r in rows
        ]
    finally:
        db.close()
