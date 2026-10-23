"""
Script ingestion offline untuk fondasi RAG figure One Piece.

Membaca dokumen markdown dari ``mcp-server/rag/knowledge/``, memecahnya menjadi
Chunk per heading, meng-embed tiap Chunk via Ollama, lalu menyimpannya ke tabel
pgvector. Strategi idempoten: hapus seluruh Chunk dokumen lama sebelum insert
ulang sehingga re-run tidak menghasilkan duplikat.

Jalankan dari direktori ``mcp-server/``::

    python -m rag.ingest
"""
import sys
from pathlib import Path

# Sisipkan direktori mcp-server/ ke sys.path agar `from config import ...`
# (dipakai tidak langsung lewat vector_store) konsisten dengan tools existing.
server_dir = str(Path(__file__).resolve().parent.parent)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from rag.embedder import embed_texts, EmbedderError
from rag.vector_store import (
    ensure_extension_and_table,
    upsert_chunk,
    delete_document_chunks,
)

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"

# Batas ukuran satu chunk sebelum dipecah lebih lanjut per paragraf.
MAX_CHUNK_CHARS = 1500


def _split_long_section(section: str) -> list[str]:
    """
    Pecah sebuah section panjang menjadi beberapa chunk per paragraf.

    Paragraf digabung berurutan sampai mendekati ``MAX_CHUNK_CHARS``. Satu
    paragraf yang sendirian melebihi batas tetap dijadikan satu chunk utuh agar
    tidak memotong kalimat di tengah.
    """
    paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= MAX_CHUNK_CHARS:
            current = current + "\n\n" + para
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks


def chunk_markdown(text: str) -> list[str]:
    """
    Pecah teks markdown menjadi daftar Chunk, satu Chunk per section heading.

    Setiap baris yang diawali ``#`` memulai section baru; heading beserta body-nya
    menjadi satu Chunk. Chunk kosong/whitespace dibuang. Section yang lebih
    panjang dari ``MAX_CHUNK_CHARS`` dipecah lebih lanjut per paragraf.
    """
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            if current:
                sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))

    chunks: list[str] = []
    for section in sections:
        stripped = section.strip()
        if not stripped:
            continue
        if len(stripped) > MAX_CHUNK_CHARS:
            chunks.extend(_split_long_section(stripped))
        else:
            chunks.append(stripped)
    return chunks


def main() -> None:
    """Jalankan proses ingestion end-to-end dan cetak ringkasan hasilnya."""
    md_files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    if not md_files:
        print("Tidak ada dokumen .md di knowledge/ untuk diindeks.")
        return

    ensure_extension_and_table()

    total_docs = 0
    total_chunks = 0
    for path in md_files:
        document = path.name
        text = path.read_text(encoding="utf-8")
        chunks = chunk_markdown(text)
        if not chunks:
            print(f"Lewati {document}: tidak ada chunk setelah pemisahan.")
            continue

        # Hapus chunk lama dokumen ini agar re-run idempoten (tanpa duplikat).
        delete_document_chunks(document)

        try:
            embeddings = embed_texts(chunks)
        except EmbedderError as e:
            print(f"Ingestion dihentikan saat memproses {document}: {e}")
            return

        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            upsert_chunk(document, i, chunk, emb)

        total_docs += 1
        total_chunks += len(chunks)

    print(f"Selesai. {total_docs} dokumen diproses, {total_chunks} chunk tersimpan.")


if __name__ == "__main__":
    main()
