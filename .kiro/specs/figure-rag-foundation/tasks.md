# Implementation Plan — figure-rag-foundation

Catatan umum untuk semua task:

- Semua path relatif ke root `Research_Fintracks_MCP`. Modul baru berada di `mcp-server/rag/`.
- Backend dan frontend TIDAK disentuh. Spec 2 (katalog produk) dan Spec 3 (UI, orkestrasi chat, toggle RAG) di luar scope.
- Lingkungan: Windows PowerShell. Jalankan perintah verifikasi dengan `cwd=mcp-server` (parameter working-directory), JANGAN memakai perintah `cd`.
- Pola import lintas-modul mengikuti `mcp-server/tools/transaction_tools.py`: sisipkan direktori `mcp-server/` ke `sys.path` lebih dulu, lalu `from config import get_db_session`.

---

- [x] 1. Buat package `rag` + modul embedder Ollama, dan tambahkan dependency `pgvector`.
      - Buat `mcp-server/rag/__init__.py` (boleh kosong, hanya penanda package).
      - Buat `mcp-server/rag/embedder.py` dengan konstanta `OLLAMA_URL = "http://localhost:11434"`, `EMBED_MODEL = "nomic-embed-text"`, `EMBED_DIM = 768`; exception kustom `class EmbedderError(Exception)`; fungsi `embed_text(text: str) -> list[float]` dan `embed_texts(texts: list[str]) -> list[list[float]]`.
      - `embed_text`: strip teks, jika kosong lempar `EmbedderError("Teks untuk embedding kosong.")`. Lakukan satu POST ke Ollama memakai `urllib.request` (standar library, tanpa dependency baru) dengan body JSON `{"model": EMBED_MODEL, "prompt": text}` ke `/api/embeddings`, baca field `embedding` dari respons. Catatan implementasi: Ollama versi baru memakai `POST /api/embed` dengan body `{"model", "input"}` dan respons `{"embeddings": [[...]]}`; verifikasi endpoint terhadap versi Ollama terpasang dan tangani kedua bentuk bila memungkinkan (coba `/api/embeddings`, fallback `/api/embed`), lalu normalkan hasil ke `list[float]`.
      - `embed_texts`: panggil `embed_text` per item, kumpulkan jadi `list[list[float]]`.
      - Penanganan error (lempar `EmbedderError` dengan pesan jelas, tidak diam-diam): Ollama mati (`urllib.error.URLError`/`ConnectionError`) -> pesan "Ollama tidak dapat dihubungi di http://localhost:11434. Pastikan Ollama berjalan."; model belum di-pull (HTTP 404 atau body memuat `not found`/`try pulling`) -> pesan "Model 'nomic-embed-text' belum tersedia. Jalankan: ollama pull nomic-embed-text"; respons tanpa field embedding atau kosong -> "Respons embedding Ollama tidak valid."; dimensi `!= EMBED_DIM` -> pesan ketidakcocokan dimensi.
      - Ubah `mcp-server/requirements.txt`: tambahkan baris `pgvector` pada daftar dependency.
      - _Prasyarat (informatif, bukan task): `ollama pull nomic-embed-text` dan pastikan Ollama berjalan di `http://localhost:11434`; jalankan `pip install -r requirements.txt` dari `mcp-server`._
      - Verifikasi: dari `mcp-server`, jalankan `python -c "from rag.embedder import embed_text, embed_texts, EmbedderError, EMBED_DIM; print(EMBED_DIM)"`. Sukses bila import berhasil tanpa error dan mencetak `768`. (Opsional bila Ollama hidup: `python -c "from rag.embedder import embed_text; print(len(embed_text('halo')))"` mencetak `768`.)
      - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 2. Buat vector store pgvector (`mcp-server/rag/vector_store.py`).
      - Di awal file sisipkan `mcp-server/` ke `sys.path` dengan pola `server_dir = str(Path(__file__).resolve().parent.parent)` lalu `sys.path.insert(0, server_dir)`, kemudian `from config import get_db_session`. Impor `from sqlalchemy import text`.
      - Definisikan `class VectorStoreError(Exception)` dan helper `_vec_literal(embedding: list[float]) -> str` yang memformat list float jadi string `'[v1,v2,...]'`.
      - `ensure_extension_and_table() -> None`: jalankan `CREATE EXTENSION IF NOT EXISTS vector;` lalu DDL `CREATE TABLE IF NOT EXISTS figure_knowledge_chunks (id SERIAL PRIMARY KEY, document TEXT NOT NULL, chunk_index INTEGER NOT NULL, content TEXT NOT NULL, embedding vector(768) NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT now(), CONSTRAINT uq_figure_chunk UNIQUE (document, chunk_index));`, lalu `commit()`. Bila `CREATE EXTENSION` gagal karena ekstensi belum terpasang (`ProgrammingError`/`OperationalError` memuat `could not open extension control file`/`extension "vector" is not available`): `rollback()` lalu lempar `VectorStoreError("Ekstensi pgvector belum terpasang di server PostgreSQL. Pasang pgvector untuk PostgreSQL terlebih dahulu sebelum fitur RAG dapat dipakai.")`. Gunakan pola sesi `db = get_db_session(); try: ...; finally: db.close()`.
      - `upsert_chunk(document, chunk_index, content, embedding) -> None`: `INSERT INTO figure_knowledge_chunks (document, chunk_index, content, embedding) VALUES (:document, :chunk_index, :content, CAST(:embedding AS vector)) ON CONFLICT (document, chunk_index) DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding`. Embedding di-bind sebagai string literal hasil `_vec_literal` lewat parameter bind (bukan interpolasi string), lalu `commit()`.
      - `delete_document_chunks(document) -> int`: `DELETE FROM figure_knowledge_chunks WHERE document = :document`, `commit()`, kembalikan jumlah baris terhapus (`result.rowcount`).
      - `similarity_search(query_embedding, top_k) -> list[dict]`: SQL `SELECT document, content, 1 - (embedding <=> CAST(:query AS vector)) AS score FROM figure_knowledge_chunks ORDER BY embedding <=> CAST(:query AS vector) LIMIT :top_k;` dengan `:query` di-bind sebagai `_vec_literal(query_embedding)`. Kembalikan `list[dict]` berisi `{"document", "content", "score"}` terurut skor tertinggi dulu.
      - Verifikasi: dari `mcp-server`, jalankan `python -c "from rag.vector_store import ensure_extension_and_table, upsert_chunk, delete_document_chunks, similarity_search, VectorStoreError; print('ok')"`. Sukses bila import berhasil tanpa error dan mencetak `ok` (modul dapat di-import tanpa menyentuh DB saat import).
      - _Prasyarat (informatif, bukan task): ekstensi pgvector perlu terpasang di server PostgreSQL `fintracks`; `CREATE EXTENSION IF NOT EXISTS vector` dijalankan oleh kode._
      - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.2, 4.3, 4.4, 1.5_

- [x] 3. Tulis dokumen seed pengetahuan (`mcp-server/rag/knowledge/figures_knowledge.md`).
      - Buat markdown terstruktur per heading agar chunking per-heading menghasilkan chunk topikal. Tulis isi nyata yang informatif (beberapa kalimat per subheading), bukan placeholder kosong.
      - Cakupan wajib: skala figure (minimal `## Skala 1/8`, `## Skala 1/7`, `## Nendoroid` di bawah heading `# Skala Figure One Piece`); brand (minimal `## Bandai`, `## Banpresto`, `## MegaHouse` di bawah `# Brand Produsen Figure`, sebutkan lini P.O.P MegaHouse untuk One Piece); bahan (`## PVC` di bawah `# Bahan Figure`); tips memilih (`# Tips Memilih Figure One Piece` dengan subheading menyesuaikan budget & skala, memverifikasi keaslian & toko tepercaya, serta merawat & memajang figure).
      - Verifikasi: dari `mcp-server`, jalankan `python -c "from pathlib import Path; p=Path('rag/knowledge/figures_knowledge.md'); t=p.read_text(encoding='utf-8'); print(p.exists(), t.count('#'), all(k in t for k in ['1/8','1/7','Nendoroid','Bandai','Banpresto','MegaHouse','PVC']))"`. Sukses bila mencetak `True`, jumlah heading `> 0`, dan `True` (semua kata kunci cakupan ada).
      - _Requirements: 6.1, 6.2, 6.3_

- [x] 4. Buat script ingestion (`mcp-server/rag/ingest.py`) yang dapat dijalankan `python -m rag.ingest`.
      - Di awal file sisipkan `mcp-server/` ke `sys.path` dengan pola yang sama seperti task 2. Impor `from rag.embedder import embed_texts, EmbedderError` dan `from rag.vector_store import ensure_extension_and_table, upsert_chunk, delete_document_chunks`.
      - `KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"`.
      - `chunk_markdown(text: str) -> list[str]`: pecah per heading markdown (baris diawali `#`); setiap section (heading + body) jadi satu chunk; buang chunk kosong/whitespace; bila section terlalu panjang (> ~1500 karakter) pecah lebih lanjut per paragraf. `chunk_index` 0-based sesuai urutan dalam dokumen.
      - `main()`: kumpulkan semua `*.md` di `KNOWLEDGE_DIR`; jika kosong cetak "Tidak ada dokumen .md di knowledge/ untuk diindeks." lalu `return` tanpa menyentuh tabel; panggil `ensure_extension_and_table()` sekali; untuk tiap file: baca teks, `chunks = chunk_markdown(text)`, `delete_document_chunks(nama_file)`, `embeddings = embed_texts(chunks)` (bila `EmbedderError` dilempar, hentikan ingestion dengan pesan jelas tanpa menyimpan embedding tak valid), lalu `upsert_chunk(nama_file, i, chunk, emb)` untuk tiap chunk; akhiri dengan ringkasan `"Selesai. N dokumen diproses, M chunk tersimpan."`. Tambahkan blok `if __name__ == "__main__": main()`.
      - _Prasyarat (informatif, bukan task): Ollama hidup + model ter-pull dan ekstensi pgvector terpasang agar ingestion end-to-end berhasil._
      - Verifikasi: dari `mcp-server`, jalankan `python -m rag.ingest`. Sukses bila tercetak ringkasan dengan jumlah chunk `> 0` tanpa error (butuh Ollama + pgvector aktif). Verifikasi import-only tanpa infra: `python -c "from rag.ingest import chunk_markdown, main; print(len(chunk_markdown('# A\nisi a\n# B\nisi b')))"` mencetak `2`.
      - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.6_

- [x] 5. Buat retriever runtime (`mcp-server/rag/retriever.py`).
      - Impor `from rag.embedder import embed_text, EmbedderError` dan `from rag.vector_store import similarity_search, VectorStoreError`.
      - `retrieve(query: str, top_k: int = 4) -> dict` mengembalikan `{"results": [{"content", "score", "document"}], "note"?}`.
      - Validasi: bila `query is None` atau `query.strip() == ""`, kembalikan `{"results": [], "note": "Query kosong. Masukkan teks pertanyaan."}` TANPA memanggil embedder/DB.
      - Normalisasi `top_k`: bila bukan int positif pakai default 4; clamp ke rentang 1..20.
      - Embed query dengan `embed_text`; `rows = similarity_search(q_emb, top_k)`; bila `rows` kosong kembalikan `{"results": [], "note": "Belum ada pengetahuan yang terindeks. Jalankan ingestion (python -m rag.ingest)."}`; selain itu map rows ke `{"results": [...]}`.
      - Tangkap `EmbedderError` dan `VectorStoreError` dan ubah menjadi `{"results": [], "note": <pesan error>}` agar tool wrapper tetap tipis dan server tidak crash.
      - Verifikasi: dari `mcp-server`, jalankan `python -c "from rag.retriever import retrieve; print(retrieve('   '))"`. Sukses bila mencetak dict dengan `results` kosong dan `note` validasi query kosong (tanpa memanggil Ollama/DB). Dengan infra aktif: `python -c "from rag.retriever import retrieve; print(retrieve('skala figure One Piece untuk pemula', top_k=4))"` mengembalikan `results` relevan terurut skor menurun; uji jalur error dengan mematikan Ollama -> hasil berupa `note` "Ollama tidak dapat dihubungi..." tanpa crash.
      - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 6. Daftarkan MCP tool `search_figure_knowledge` di `mcp-server/server.py`.
      - Tambahkan import `from rag.retriever import retrieve` di dekat import tools lain (import berfungsi tanpa perubahan `sys.path` tambahan karena `server.py` sudah menyisipkan `server_dir`).
      - Tambahkan satu fungsi `@mcp.tool() def search_figure_knowledge(query: str, top_k: int = 4) -> str` sebagai thin wrapper: docstring menjelaskan fungsinya (mencari pengetahuan figure One Piece: skala/brand/bahan/tips, parameter `query` dan `top_k` default 4); bungkus panggilan `retrieve(query, top_k)` dalam `try/except Exception` agar tidak meng-crash server; bila hasil punya `results` kosong kembalikan `note` (atau pesan default); selain itu format tiap hasil jadi baris terbaca `"[i] (skor X, sumber: dokumen)\n<content>"` dengan header jumlah hasil. Jangan ubah registrasi tool lain (transaction/gatling).
      - Verifikasi: dari `mcp-server`, jalankan `python -c "import server; print('search_figure_knowledge' in dir(server))"`. Sukses bila mencetak `True` dan modul `server` ter-import tanpa error (artinya tool lain tidak rusak). Verifikasi perilaku ringan: `python -c "import server; print(server.search_figure_knowledge('   '))"` mengembalikan string pesan note, bukan exception.
      - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 7. Verifikasi integrasi end-to-end fondasi RAG.
      - Pastikan prasyarat aktif (informatif): Ollama berjalan dengan `nomic-embed-text` ter-pull, ekstensi pgvector terpasang di PostgreSQL `fintracks`, dan `pip install -r requirements.txt` sudah dijalankan dari `mcp-server`.
      - Jalankan ingestion lalu retrieval untuk membuktikan alur offline -> runtime tersambung. Tidak ada perubahan kode baru di task ini; bila ada error, perbaiki di modul terkait (task 1–6).
      - Verifikasi (cwd=mcp-server, JANGAN pakai `cd`):
        - `python -m rag.ingest` -> sukses bila ringkasan chunk `> 0`.
        - `python -c "from rag.retriever import retrieve; r=retrieve('skala figure One Piece untuk pemula', top_k=4); print(len(r['results']), [round(x['score'],3) for x in r['results']])"` -> sukses bila `results` berisi chunk relevan terurut skor menurun.
        - Jalur error: matikan Ollama lalu `python -c "from rag.retriever import retrieve; print(retrieve('tes'))"` -> sukses bila mengembalikan `note` "Ollama tidak dapat dihubungi..." tanpa crash; `python -c "from rag.retriever import retrieve; print(retrieve('   '))"` -> sukses bila `note` validasi query kosong tanpa memanggil Ollama/DB.
      - _Requirements: 1.7, 4.3, 4.5, 4.6, 5.4, 5.5_
