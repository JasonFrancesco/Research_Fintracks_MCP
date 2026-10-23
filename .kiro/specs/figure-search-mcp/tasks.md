# Implementation Plan

Rencana implementasi untuk fitur `figure-search-mcp` (Spec 2). Mengikuti design final apa adanya: satu MCP tool baru `search_figures` yang membaca katalog produk figure One Piece dari seed JSON lokal lewat lapisan `Catalog_Adapter`. Hanya menyentuh `mcp-server/` (seed JSON, dua modul tools baru, satu tambahan thin wrapper di `server.py`). Tidak menyentuh `backend/`, `frontend/`, `mcp-server/rag/`, `transaction_tools.py`, `gatling_tools.py`, maupun `config.py`. Tidak ada dependency baru (cukup `json` + `pathlib` stdlib). Semua perintah verifikasi dijalankan dengan cwd `mcp-server/` (PowerShell Windows), jangan pakai `cd` dalam perintah.

- [x] 1. Buat katalog seed lokal `figures_seed.json`.
      - Buat file `mcp-server/data/figures_seed.json` berisi array JSON Figure_Record.
      - Setiap record memuat field: `id`, `nama`, `karakter`, `brand`, `skala`, `tinggi_cm` (angka), `harga` (angka Rupiah tanpa simbol), `stok` (angka), `image_url` (URL gambar), `shopee_url` (tautan).
      - Minimal memuat karakter Luffy, Zoro, dan Nami; boleh ditambah Sanji dan/atau Ace. Setiap entri terisi lengkap pada semua field wajib.
      - Pakai `id` unik dan deterministik per entri (mis. `op-luffy-001`, `op-zoro-001`, `op-nami-001`), nilai `harga`/`stok` sebagai integer dan `tinggi_cm` sebagai angka; URL boleh placeholder (status placeholder ditegaskan nanti di komentar `figure_catalog.py`).
      - Verifikasi: `python -c "import json,pathlib; d=json.loads(pathlib.Path('data/figures_seed.json').read_text(encoding='utf-8')); print(len(d), sorted({r['karakter'] for r in d}))"` — mencetak jumlah record dan daftar karakter yang mencakup minimal Luffy, Nami, Zoro.
      - (Manual, informatif) Buka file dan pastikan JSON valid serta setiap record punya 9 field wajib + `id`.
      - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 2. Buat Catalog_Adapter `figure_catalog.py`.
      - Buat file `mcp-server/tools/figure_catalog.py` dengan komentar kepala file yang menegaskan: ini satu-satunya titik tukar menuju Shopee API dan katalog saat ini berstatus placeholder.
      - Definisikan `class CatalogError(Exception)`, konstanta `REQUIRED_FIELDS = ("nama", "karakter", "brand", "skala", "tinggi_cm", "harga", "stok", "image_url", "shopee_url")`, dan `SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "figures_seed.json"`.
      - Implementasikan `load_catalog() -> list[dict]`: baca `SEED_PATH` dengan `open(..., encoding="utf-8")`; file tidak ada → `raise CatalogError` pesan jelas menyebut path; JSON rusak → `raise CatalogError` pesan "tidak dapat dibaca"; root bukan `list` → `raise CatalogError` pesan "format tidak valid (harus array)"; root `list` kosong → kembalikan `[]` (bukan error).
      - Untuk tiap entri: normalkan `harga` dan `stok` ke `int`, `tinggi_cm` ke `float`, dan pastikan `id` ada (generate dari indeks jika tidak ada). Jangan menerapkan filter/sort di adapter (itu tugas `figure_tools`).
      - Verifikasi: `python -c "from tools.figure_catalog import load_catalog; r=load_catalog(); print(len(r), type(r[0]['harga']).__name__, type(r[0]['tinggi_cm']).__name__, 'id' in r[0])"` — mencetak jumlah record, `int`, `float`, dan `True`.
      - _Requirements: 2.1, 2.2, 2.3, 2.4, 5.1, 5.2, 6.4_

- [x] 3. Buat Figure_Tools_Module `figure_tools.py`.
      - Buat file `mcp-server/tools/figure_tools.py` dengan `from tools.figure_catalog import load_catalog, CatalogError` dan `import json`.
      - Implementasikan `search_figures_tool(query="", max_price=None, min_height=None, max_height=None, brand=None, limit=5) -> str` mengikuti alur tetap: (1) validasi sebelum load — `max_price < 0`, `min_height < 0`, `max_height < 0`, `min_height > max_height` (bila keduanya ada), `limit <= 0` → kembalikan JSON error validasi tanpa menjalankan pencarian; (2) `records = load_catalog()` dibungkus `try/except CatalogError` → JSON `{count:0, results:[], error:...}`, dan `except Exception` umum juga → JSON error agar server tidak crash; (3) `records == []` → JSON `{count:0, results:[], message:"Katalog figure kosong."}`.
      - Lanjutan alur: (4) keyword match `q = query.strip().lower()` — kosong = semua kandidat, selain itu record yang `nama` ATAU `karakter` (lowercase) mengandung `q`, dengan skor relevansi deterministik (match `karakter`/awalan `nama` > substring biasa); (5) filter AND `harga <= max_price`, `tinggi_cm >= min_height`, `tinggi_cm <= max_height`, `brand.lower() == brand_param.lower()`, filter `None` dilewati; (6) sort deterministik `(skor menurun, harga menaik, id menaik)`; (7) kandidat kosong setelah filter → JSON `{count:0, results:[], message:"Tidak ada figure yang cocok dengan kriteria."}`; (8) `results[:limit]`; (9) format `json.dumps({"count":..., "results":[...]}, ensure_ascii=False)` dengan tiap hasil memuat semua field wajib + `id` dan `harga` sebagai angka Rupiah.
      - Verifikasi: `python -c "from tools.figure_tools import search_figures_tool; import json; print(json.loads(search_figures_tool(query='Luffy'))['count'])"` — mencetak angka `>= 1`.
      - Verifikasi: `python -c "from tools.figure_tools import search_figures_tool; import json; r=json.loads(search_figures_tool(query='', max_price=400000)); print(all(x['harga'] <= 400000 for x in r['results']))"` — mencetak `True`.
      - Verifikasi: `python -c "from tools.figure_tools import search_figures_tool; import json; print('error' in json.loads(search_figures_tool(max_price=-1)), 'error' in json.loads(search_figures_tool(limit=0)), 'error' in json.loads(search_figures_tool(min_height=30, max_height=10)))"` — mencetak `True True True` (JSON error validasi, pencarian tidak dijalankan).
      - Verifikasi: `python -c "from tools.figure_tools import search_figures_tool; import json; r=json.loads(search_figures_tool(query='karakter-yang-tidak-ada')); print(r['count'], r.get('message'))"` — mencetak `0` dengan pesan eksplisit "Tidak ada figure yang cocok dengan kriteria.".
      - (Manual, opsional informatif) Ganti sementara nama `data/figures_seed.json`, jalankan `search_figures_tool(query='Luffy')` → JSON memuat `error` "katalog tidak tersedia" dan proses Python tidak crash; kembalikan nama file setelahnya.
      - _Requirements: 1.3, 1.4, 1.5, 2.1, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [x] 4. Daftarkan MCP tool `search_figures` di `server.py`.
      - Ubah `mcp-server/server.py`: tambahkan `from tools.figure_tools import search_figures_tool` di blok import tools yang sudah ada (`Optional` sudah terimpor di file ini).
      - Tambahkan satu `@mcp.tool() def search_figures(query="", max_price=None, min_height=None, max_height=None, brand=None, limit=5) -> str` setelah `search_figure_knowledge`, sebagai thin wrapper yang hanya `return search_figures_tool(...)` (tanpa logika lain).
      - Tulis docstring jelas: kapan memakai `search_figures` (ingin membeli/melihat produk figure beserta harga & stok) vs `search_figure_knowledge` (pertanyaan pengetahuan: skala/brand/bahan/tips); jelaskan arti tiap parameter (`query`, `max_price`, `min_height`, `max_height`, `brand`, `limit`) dan sebutkan return berupa JSON string `{count, results}`.
      - Jangan ubah tool lain (transaction, gatling, `search_figure_knowledge`).
      - Verifikasi: `python -c "import server; print('search_figures' in dir(server))"` — mencetak `True` tanpa error impor.
      - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6_

- [x] 5. Verifikasi integrasi end-to-end tool di MCP server.
      - Tidak ada perubahan kode pada task ini; hanya memastikan seluruh potongan Spec 2 tersambung dan tool existing tetap utuh.
      - Verifikasi: `python -c "import server; print('search_figures' in dir(server), 'search_figure_knowledge' in dir(server), 'create_transaction' in dir(server))"` — mencetak `True True True` (tool baru terdaftar, tool existing tidak terganggu).
      - Verifikasi: `python -c "import server, json; print(json.loads(server.search_figures(query='Nami', limit=5))['count'] >= 1)"` — mencetak `True` (wrapper memanggil logika tool dengan benar dan mengembalikan JSON yang bisa di-parse).
      - (Manual, opsional informatif) Jalankan `python -c "import server, json; r=json.loads(server.search_figures(query='Luffy')); print(set(('nama','karakter','brand','skala','tinggi_cm','harga','stok','image_url','shopee_url','id')) <= set(r['results'][0].keys()))"` → `True`, memastikan tiap hasil berfield lengkap untuk konsumen Spec 3.
      - _Requirements: 1.1, 1.6, 4.1, 4.2, 4.3_
