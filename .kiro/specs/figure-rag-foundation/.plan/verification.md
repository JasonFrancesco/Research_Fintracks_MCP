# Verifikasi — figure-rag-foundation

Semua perintah dijalankan dengan `cwd=mcp-server`
(`d:\BINUS SEMESTER 7\Calpadia Sistem Integrasi\sourcecode\Research_Fintracks_MCP\mcp-server`),
Windows PowerShell, tanpa `cd`. Iterasi pertama (tidak ada `review.json`), implementasi dari awal.

## Ringkasan bukti nyata

- **Dimensi embedding nyata** `nomic-embed-text` = **768** → cocok dengan `EMBED_DIM=768` dan kolom `vector(768)` di DDL. Tidak ada penyesuaian dimensi yang diperlukan.
- **Ingestion**: **1 dokumen** (`figures_knowledge.md`) diproses, **14 chunk** tersimpan ke tabel `figure_knowledge_chunks`.
- **Retrieval** query "skala figure One Piece untuk pemua": 4 hasil, skor menurun **[0.905, 0.875, 0.845, 0.835]**, hasil teratas topikal (section "Skala Figure One Piece" dan "Skala 1/8").
- **Endpoint Ollama**: jalur utama `/api/embed` / `/api/embeddings` dinormalkan ke `list[float]`; embedder mencoba `/api/embeddings` lalu fallback `/api/embed`. Pada mesin ini embedding berhasil mengembalikan vektor 768-dim.

## Perintah & hasil

### 1. `pip install -r requirements.txt`
Sukses. `pgvector-0.5.1` ter-install; dependency lain sudah terpenuhi. Exit 0.

### 2. Import-only tiap modul
```
python -c "from rag.embedder import embed_text, embed_texts, EmbedderError, EMBED_DIM; print('embedder', EMBED_DIM)"   -> embedder 768
python -c "from rag.vector_store import ensure_extension_and_table, upsert_chunk, delete_document_chunks, similarity_search, VectorStoreError; print('vector_store ok')"  -> vector_store ok
python -c "from rag.retriever import retrieve; print('retriever ok')"  -> retriever ok
python -c "from rag.ingest import chunk_markdown, main; print('ingest chunks', len(chunk_markdown('# A\nisi a\n# B\nisi b')))"  -> ingest chunks 2
```
Semua import murni tanpa menyentuh DB. Exit 0.

### 3. Embed nyata
```
python -c "from rag.embedder import embed_text; print(len(embed_text('halo')))"  -> 768
```

### 4. Ingestion
```
python -m rag.ingest  -> Selesai. 1 dokumen diproses, 14 chunk tersimpan.
```

### 5. Retrieval (ranking)
```
python -c "from rag.retriever import retrieve; r=retrieve('skala figure One Piece untuk pemula', top_k=4); print(len(r['results']), [round(x['score'],3) for x in r['results']])"
  -> 4 [0.905, 0.875, 0.845, 0.835]
```
Konten hasil teratas: `# Skala Figure One Piece ...`, `## Skala 1/8 ...` (relevan, terurut skor menurun).

### 6. Jalur error — query kosong/spasi
```
python -c "from rag.retriever import retrieve; print(retrieve('   '))"
  -> {'results': [], 'note': 'Query kosong. Masukkan teks pertanyaan.'}
```
Tidak memanggil Ollama/DB.

### 7. Server import & tool
```
python -c "import server; print('search_figure_knowledge' in dir(server)); print(server.search_figure_knowledge('   '))"
  -> True
  -> Query kosong. Masukkan teks pertanyaan.
```
`server` ter-import tanpa error (tool transaction/gatling tidak rusak); tool baru terdaftar dan mengembalikan string note, bukan exception.

### Cek dokumen seed
```
python -c "from pathlib import Path; p=Path('rag/knowledge/figures_knowledge.md'); t=p.read_text(encoding='utf-8'); print(p.exists(), t.count('#')>0, all(k in t for k in ['1/8','1/7','Nendoroid','Bandai','Banpresto','MegaHouse','PVC']))"
  -> True True True
```

## Catatan scope
- Hanya `mcp-server/` yang disentuh. `backend/` dan `frontend/` tidak diubah.
- Registrasi tool lain (transaction/gatling) di `server.py` tidak diubah; hanya ditambah satu import `from rag.retriever import retrieve` dan satu `@mcp.tool() def search_figure_knowledge`.
- `install_pgvector.ps1` dibiarkan apa adanya. Tidak ada file sementara yang tertinggal.
