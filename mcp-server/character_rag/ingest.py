"""
=============================================================================
 CHARACTER RAG — INGESTION (ingest.py)
=============================================================================
Script OFFLINE idempoten yang membangun Persisted Vector Database pengetahuan
karakter One Piece dari dokumen PDF resmi:
"ENSIKLOPEDIA ARSIP DATA 50 KARAKTER ONE PIECE"
memakai LlamaIndex + embedding multilingual ``BAAI/bge-m3`` (1024 dimensi).

Alur RAG Pipeline:
1. INGESTION & PREPROCESSING: Membaca PDF via adapter.load_characters()
   (ekstraksi teks multi-halaman, pembersihan ligatur/simbol, dan parsing entitas).
2. CHUNKING (Opsi A — Sentence/Token Splitter): Setiap entitas karakter dibentuk
   menjadi Document naratif lengkap dengan metadata (id, nama, peran, afiliasi,
   bounty, buah iblis, halaman), lalu dipecah oleh ``SentenceSplitter`` menjadi
   satu atau beberapa node berukuran tetap (chunk_size) dengan overlap antar node.
   Metadata karakter diwarisi ke setiap node sehingga potongan tetap terpetakan ke
   karakter asalnya untuk fusi dengan skor leksikal di tahap retrieval.
3. EMBEDDING: Menggunakan SOTA multilingual BAAI/bge-m3 untuk mengonversi teks ke vektor 1024-dim.
4. VECTOR DATABASE PERSISTENCE: Menyimpan vektor ke PostgreSQL + pgvector
   (tabel data_onepiece_characters), menggantikan penyimpanan file JSON lama.

Jalankan dari direktori ``mcp-server`` dengan:

    python -m character_rag.ingest
=============================================================================
"""
import os
import sys
from pathlib import Path

# Aktifkan mode offline agar menggunakan cache model lokal tanpa timeout jaringan
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Sisipkan server_dir (= mcp-server/) ke sys.path agar impor
# `from character_rag.adapter import ...` bekerja sama seperti modul lain.
server_dir = str(Path(__file__).resolve().parent.parent)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from llama_index.core import VectorStoreIndex, Settings, Document, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from character_rag.adapter import load_characters, CharacterAdapterError
from character_rag.vector_store import get_pg_vector_store, ensure_vector_extension

EMBED_MODEL_NAME = "BAAI/bge-m3"

# =============================================================================
# PARAMETER CHUNKING (Opsi A: Sentence/Token Splitter)
# =============================================================================
# chunk_size   = jumlah token maksimum per potongan (node). Dokumen karakter yang
#                "Kisah"-nya panjang dipecah menjadi beberapa node agar vektor tiap
#                potongan lebih fokus (embedding tidak "tercampur" jadi rata-rata).
# chunk_overlap= token yang di-overlap antar potongan agar konteks di batas potongan
#                tidak terputus. Keduanya bisa dieksperimenkan (256/512/1024) sebagai
#                variabel riset untuk mengukur dampak ke Context Relevance.
# Dibaca dari .env supaya bisa diubah tanpa menyentuh kode.
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "256"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "32"))


# =============================================================================
# TAHAP 1: PROSES CHUNKING (Pemotongan / Pembentukan Dokumen Teks Naratif)
# =============================================================================
def build_document(record: dict) -> Document:
    """
    [CHUNKING PROSES]
    Ubah satu entitas record karakter dari PDF menjadi satu Document/Chunk naratif.
    Kalimat naratif kaya konteks (biografi, asal usul, peran, bounty, buah iblis,
    senjata, rekam jejak) membuat model embedding memahami makna relasi karakter,
    sehingga pencarian semantik (semantic search) menjadi jauh lebih akurat.
    """
    if record.get("text_chunk"):
        text = record["text_chunk"]
    else:
        nama = record.get("Nama", "")
        julukan = record.get("Julukan", "")
        peran = record.get("Peran", "")
        afil = record.get("Afiliasi", "")
        asal = record.get("Asal Usul", "")
        bounty = record.get("Bounty (Beli)", "")
        buah = record.get("Buah Iblis", "")
        senjata = record.get("Kemampuan", "")
        kisah = record.get("Kisah", "")
        hal = record.get("Halaman", 1)

        text = (
            f"Karakter: {nama}" + (f" (dijuluki {julukan})" if julukan else "") + f". "
            f"Peran: {peran}. Afiliasi: {afil}. "
            + (f"Asal usul: {asal}. " if asal else "")
            + (f"Nilai bounty: {bounty}. " if bounty else "")
            + (f"Buah Iblis: {buah}. " if buah else "Buah Iblis: Tidak Ada. ")
            + (f"Senjata / Kemampuan utama: {senjata}. " if senjata else "")
            + (f"Kisah & Rekam Jejak Sejarah (berdasarkan PDF): {kisah}" if kisah else "")
            + f" [Sumber: Dokumen PDF Halaman {hal}]"
        )

    metadata = {
        "id": str(record.get("ID", "")),
        "nama": str(record.get("Nama", "")),
        "julukan": str(record.get("Julukan", "")),
        "peran": str(record.get("Peran", "")),
        "afiliasi": str(record.get("Afiliasi", "")),
        "bagian": str(record.get("Bagian", "")),
        "asal_usul": str(record.get("Asal Usul", "")),
        "bounty": str(record.get("Bounty (Beli)", "")),
        "buah_iblis": str(record.get("Buah Iblis", "")),
        "halaman": int(record.get("Halaman", 1)),
        "source": "one-piece-characters.pdf",
    }

    return Document(text=text.strip(), metadata=metadata)


def main() -> None:
    print("=================================================================")
    print("  CHARACTER RAG INGESTION — PDF ENGINE (BAAI/bge-m3)")
    print("=================================================================")

    try:
        # =========================================================================
        # TAHAP 1: INGESTING & PREPROCESSING DARI DOKUMEN PDF
        # =========================================================================
        print("[1/4] Mengekstrak dan memproses teks dari dokumen PDF...")
        records = load_characters()
    except CharacterAdapterError as e:
        print(f"Ingestion dibatalkan: {e}")
        return

    if not records:
        print("Tidak ada karakter untuk diindeks.")
        return

    print(f"      Berhasil mengekstrak {len(records)} data karakter dari dokumen PDF.")

    # =========================================================================
    # TAHAP 2: CHUNKING & MEMBANGUN DOKUMEN SEMANTIK
    # =========================================================================
    print("[2/4] Melakukan chunking naratif berkonteks tinggi (metadata + biografi)...")
    documents = [build_document(r) for r in records]

    # =========================================================================
    # TAHAP 3: INISIALISASI MODEL EMBEDDING (BAAI/bge-m3) + SENTENCE SPLITTER
    # =========================================================================
    print(f"[3/4] Inisialisasi model embedding multilingual: {EMBED_MODEL_NAME}...")
    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)

    # Opsi A: pecah Document panjang menjadi beberapa node dengan ukuran tetap +
    # overlap. Metadata Document (id, nama, halaman, dst.) otomatis diwarisi setiap
    # node hasil pemecahan, sehingga potongan tetap bisa dipetakan balik ke karakter.
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(documents)
    print(f"      Chunking: {len(documents)} dokumen karakter -> {len(nodes)} node "
          f"(chunk_size={CHUNK_SIZE}, chunk_overlap={CHUNK_OVERLAP}).")

    # =========================================================================
    # TAHAP 4: EMBEDDING (batch) & MENULIS KE VECTOR DATABASE (PostgreSQL + pgvector)
    # =========================================================================
    # Catatan: kita meng-embed seluruh node dalam SATU batch lalu menulisnya via
    # vector_store.add(), bukan lewat VectorStoreIndex(nodes, ...). Pola batch ini
    # jauh lebih cepat & stabil daripada membiarkan index meng-embed + insert node
    # satu per satu (yang di Windows + koneksi async bisa sangat lambat).
    print(f"[4/4] Meng-embed {len(nodes)} node (batch) lalu menyimpan ke PostgreSQL (pgvector)...")

    texts = [n.get_content(metadata_mode="all") for n in nodes]
    embeddings = Settings.embed_model.get_text_embedding_batch(texts, show_progress=True)
    for node, emb in zip(nodes, embeddings):
        node.embedding = emb
    print(f"      Embedding selesai untuk {len(embeddings)} node.")

    ensure_vector_extension()
    vector_store = get_pg_vector_store(perform_setup=True)

    # Tabel dibangun ulang dari awal agar ingestion idempoten (hapus isi lama dulu).
    try:
        vector_store.clear()
    except Exception as e:
        print(f"      (info) tidak dapat mengosongkan tabel lama: {str(e)[:80]}")

    vector_store.add(nodes)

    print(f"\n[SUKSES] {len(documents)} dokumen karakter dari PDF berhasil dipecah "
          f"menjadi {len(nodes)} node chunk dan disimpan ke PostgreSQL (pgvector)!")
    print(f"Tabel vektor: data_onepiece_characters (database: fintracks)")


if __name__ == "__main__":
    main()
