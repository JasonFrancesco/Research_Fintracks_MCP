# Implementation Plan — character-rag-llamaindex

Catatan umum:
- Semua perintah verifikasi dijalankan dari direktori `mcp-server` (cwd = `mcp-server`). Pada PowerShell Windows set cwd lewat opsi runner, JANGAN pakai `cd`.
- CSV sudah ada di `mcp-server/data/one-piece-characters.csv` (50 baris, kolom: `ID, Nama, Julukan, Afiliasi, Peran, Bounty (Beli), Buah Iblis, Tipe Buah Iblis`). Jangan diubah.
- RAG lama (`rag/` pgvector, tool `search_figure_knowledge`) dan fitur figure (`search_figures`) DIBIARKAN apa adanya. Jangan diubah/dihapus.
- Hanya task CODING. Verifikasi manual ditulis sebagai sub-bullet informatif, bukan task tersendiri.
- Urutan sadar-dependency: Task 3–5 butuh `llama-index` + `sentence-transformers` terpasang (Task 2). Task 4 verifikasi nyata butuh index sudah dibangun (Task 3).

- [x] 1. Tambah dependency, buat package `character_rag`, dan buat `adapter.py`
      - Ubah `mcp-server/requirements.txt`: tambah tiga baris `llama-index`, `llama-index-embeddings-huggingface`, `sentence-transformers` (tanpa menghapus baris existing).
      - Buat `mcp-server/character_rag/__init__.py` kosong (penanda package).
      - Buat `mcp-server/character_rag/adapter.py`: `class CharacterAdapterError(Exception)`; `CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "one-piece-characters.csv"`; `FIELDS` tuple 8 kolom sesuai header CSV; `load_characters() -> list[dict]` memakai `csv.DictReader` dengan `encoding="utf-8"` dan `newline=""`, tiap nilai di-`strip()`; bila `CSV_PATH` tidak ada raise `CharacterAdapterError` (sertakan path); bungkus `OSError` menjadi `CharacterAdapterError`. Tanda tangan `load_characters()` dikunci sebagai titik tukar sumber data.
      - Catatan dependency: adapter TIDAK butuh llama-index sehingga bisa diuji mandiri sebelum instalasi di Task 2.
      - Files: `mcp-server/requirements.txt`, `mcp-server/character_rag/__init__.py`, `mcp-server/character_rag/adapter.py`
      - Verify (cwd=`mcp-server`): `python -c "from character_rag.adapter import load_characters; c=load_characters(); print(len(c), c[0]['Nama'])"` → cetak `50 Monkey D. Luffy`.
      - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Pasang dependency baru dan pastikan tool lama tidak rusak
      - Jalankan `pip install -r requirements.txt` dari `mcp-server` untuk memasang `llama-index`, `llama-index-embeddings-huggingface`, dan `sentence-transformers` (menarik `torch` yang besar — instalasi bisa LAMA).
      - Setelah instalasi, buktikan `import server` MASIH berhasil → memastikan penambahan paket tidak mematikan tool existing (transaksi, gatling, `search_figures`, `search_figure_knowledge`). Bila muncul konflik versi, pin versi yang kompatibel di `requirements.txt` lalu install ulang.
      - Catatan dependency: Task ini WAJIB selesai sebelum Task 3–5 karena modul ingest/retriever meng-import `llama_index` dan `llama_index.embeddings.huggingface`.
      - Files: (hanya instalasi lingkungan; edit `requirements.txt` hanya bila perlu pin versi)
      - Verify (cwd=`mcp-server`): `pip install -r requirements.txt` selesai tanpa error; lalu `python -c "import server; print('ok')"` → cetak `ok`.
      - _Requirements: 3.2, 3.4, 5.6_

- [x] 3. Buat `ingest.py` (pembangunan + persist indeks offline)
      - Buat `mcp-server/character_rag/ingest.py`: sisipkan `server_dir` (`mcp-server`) ke `sys.path`; `from llama_index.core import VectorStoreIndex, Settings, Document`; `from llama_index.embeddings.huggingface import HuggingFaceEmbedding`; `from character_rag.adapter import load_characters, CharacterAdapterError`.
      - Konstanta: `STORAGE_DIR = Path(__file__).resolve().parent / "storage"`; `EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"`.
      - `build_document(record) -> Document`: teks naratif `"{Nama}, dijuluki {Julukan}, adalah {Peran} dari {Afiliasi}. Bounty-nya {Bounty (Beli)} Berry. Buah iblis: {Buah Iblis}"` lalu tambahkan `" (tipe {Tipe Buah Iblis})."` bila tipe terisi dan `!= "-"`, selain itu akhiri dengan `"."`; metadata `{"id": record["ID"], "nama": record["Nama"]}`.
      - `main()`: set `Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)`; `records = load_characters()` dibungkus `try/except CharacterAdapterError` → print pesan & `return`; bila `records` kosong → print & `return`; `documents = [build_document(r) for r in records]`; `index = VectorStoreIndex.from_documents(documents)`; `index.storage_context.persist(persist_dir=str(STORAGE_DIR))`; cetak jumlah dokumen + lokasi `STORAGE_DIR`. Tambah blok `if __name__ == "__main__": main()` agar jalan via `python -m character_rag.ingest`.
      - Catatan dependency: butuh Task 2; menjalankan ingestion mengunduh model `all-MiniLM-L6-v2` sekali (bisa LAMA).
      - Files: `mcp-server/character_rag/ingest.py`
      - Verify (cwd=`mcp-server`): `python -c "from character_rag.ingest import build_document; d=build_document({'ID':'1','Nama':'Monkey D. Luffy','Julukan':'Straw Hat','Afiliasi':'Straw Hat Pirates','Peran':'Captain','Bounty (Beli)':'3,000,000,000','Buah Iblis':'Hito Hito no Mi','Tipe Buah Iblis':'Mythical Zoan'}); print(d.text); print(d.metadata)"` → teks naratif memuat nama/bounty/buah iblis + metadata `{'id':'1','nama':'Monkey D. Luffy'}`.
      - Verify (cwd=`mcp-server`): `python -m character_rag.ingest` → cetak `50 dokumen karakter diindeks` + lokasi storage; folder `character_rag/storage/` terisi file index (`docstore.json`, `index_store.json`, `default__vector_store.json`).
      - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.1, 3.3, 3.5_

- [x] 4. Buat `retriever.py` (retrieval semantik runtime)
      - Buat `mcp-server/character_rag/retriever.py`: `from llama_index.core import StorageContext, load_index_from_storage, Settings`; `from llama_index.embeddings.huggingface import HuggingFaceEmbedding`. Konstanta `STORAGE_DIR` & `EMBED_MODEL_NAME` sama dengan `ingest.py`; `DEFAULT_TOP_K = 4`, `MIN_TOP_K = 1`, `MAX_TOP_K = 20`; cache modul `_index = None`.
      - `_normalize_top_k(top_k)`: int non-valid/kurang dari MIN → `DEFAULT_TOP_K`; selain itu clamp ke `MAX_TOP_K`.
      - `_load_index()`: bila `_index is None`, set `Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)` (identik dengan ingestion), lalu `StorageContext.from_defaults(persist_dir=str(STORAGE_DIR))` + `load_index_from_storage(ctx)`, simpan ke cache.
      - `retrieve(query, top_k=DEFAULT_TOP_K) -> dict`: query `None`/kosong/spasi → `{"results": [], "note": "Query kosong. Masukkan teks pertanyaan."}` TANPA memuat index/embedder; bila `STORAGE_DIR` tidak ada → `{"results": [], "note": "Indeks karakter belum dibangun. Jalankan: python -m character_rag.ingest"}`; normalize `top_k`; `try: index.as_retriever(similarity_top_k=k).retrieve(str(query))` `except Exception as e:` → `{"results": [], "note": f"Gagal melakukan retrieval karakter: {e}"}`; map tiap node ke `{"text": n.node.get_content(), "id": n.node.metadata.get("id"), "nama": n.node.metadata.get("nama"), "score": float(n.score) if n.score is not None else None}`.
      - Catatan dependency: verifikasi retrieval NYATA butuh index dari Task 3; verifikasi query kosong tidak butuh index/model.
      - Files: `mcp-server/character_rag/retriever.py`
      - Verify (cwd=`mcp-server`): `python -c "from character_rag.retriever import retrieve; print(retrieve('   '))"` → mengembalikan dict dengan `results: []` + note validasi, tanpa memuat model.
      - Verify (cwd=`mcp-server`): `python -c "from character_rag.retriever import retrieve; r=retrieve('ceritakan tentang Trafalgar Law', top_k=3); print(len(r['results']), [x['nama'] for x in r['results']])"` → maksimal 3 hasil dan Trafalgar Law muncul di daftar nama.
      - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 3.3_

- [x] 5. Daftarkan MCP tool `search_onepiece_characters` di `server.py`
      - Ubah `mcp-server/server.py`: tambah `from character_rag.retriever import retrieve as retrieve_characters` (ALIAS agar tidak bentrok dengan `from rag.retriever import retrieve` yang sudah ada).
      - Tambah `@mcp.tool() def search_onepiece_characters(query: str, top_k: int = 4) -> str` sebagai thin wrapper, mengikuti pola `search_figure_knowledge`. Docstring menjelaskan tool khusus PENGETAHUAN karakter One Piece (nama/julukan/afiliasi/peran/bounty/buah iblis), beri contoh pertanyaan, dan BEDAKAN dari `search_figures` (produk/beli), `search_figure_knowledge` (pengetahuan figure), serta tool transaksi (keuangan).
      - Body: `try: result = retrieve_characters(query, top_k)` `except Exception as e:` → `f"Gagal mencari pengetahuan karakter: {str(e)}"`. Ambil `note` dan `rows = result.get("results", [])`; bila `rows` kosong → kembalikan `note` atau `"Tidak ada karakter relevan yang ditemukan."`; selain itu bangun header `f"Ditemukan {len(rows)} karakter relevan:"` lalu tiap baris `f"[{i}] {nama} (ID {id}, skor {score:.3f})\n{text}"` (skor `"-"` bila `None`).
      - JANGAN mengubah tool lain maupun import existing.
      - Files: `mcp-server/server.py`
      - Verify (cwd=`mcp-server`): `python -c "import server; print('search_onepiece_characters' in dir(server), 'search_figures' in dir(server), 'search_figure_knowledge' in dir(server))"` → `True True True`.
      - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [x] 6. Verifikasi integrasi akhir (end-to-end non-blocking)
      - Jalankan ulang rangkaian verifikasi berurutan untuk memastikan seluruh jalur ingestion → retrieval → tool berfungsi dan tidak merusak tool lama. JANGAN menjalankan MCP server/backend sebagai proses blocking long-running.
      - Verify (cwd=`mcp-server`): `python -c "from character_rag.adapter import load_characters; print(len(load_characters()))"` → `50`.
      - Verify (cwd=`mcp-server`): `python -c "from character_rag.retriever import retrieve; r=retrieve('siapa kapten Straw Hat', top_k=2); print([x['nama'] for x in r['results']])"` → mengembalikan karakter relevan (Luffy diharapkan muncul).
      - Verify (cwd=`mcp-server`): `python -c "import server; print(all(t in dir(server) for t in ['search_onepiece_characters','search_figures','search_figure_knowledge','create_transaction','generate_gatling_script']))"` → `True` (tool baru terdaftar, tool lama utuh).
      - _Requirements: 2.8, 4.3, 5.6_
