# Implementation Plan

Rencana ini mengikat tool Spec 1 (`search_figure_knowledge`) dan Spec 2 (`search_figures`) menjadi pengalaman end-to-end di halaman One Piece, sesuai design yang sudah disetujui. Hanya DUA file aplikasi yang diubah (`backend/app/routes/chat.py`, `frontend/src/components/Chatbot.jsx`) plus SATU file baru (`frontend/src/components/FigureProductCard.jsx`). `mcp-server/**`, `schema_adapter.py`, `App.jsx`, `pages/OnePiece.jsx`, `services/api`, model backend lain, dan endpoint `/chat/history` & `/chat/models` TIDAK disentuh. Semua perubahan backward-compatible: field request/response baru bersifat opsional, perubahan frontend dikondisikan `theme === 'onepiece'`.

Urutan task bersifat incremental: tiap task menjaga backend tetap bisa di-import dan frontend tetap bisa di-build. Task 1-4 backend, task 5-6 frontend, task 7 verifikasi integrasi.

- [x] 1. Perluas model `ChatRequest`/`ChatResponse` dan resolusikan default `use_rag` di `chat_with_ai`.
      - Di `backend/app/routes/chat.py`, pada class `ChatRequest` tambahkan field `use_rag: Optional[bool] = None` (setelah `model`). `None` = pakai default endpoint (ON), bukan error.
      - Pada class `ChatResponse` tambahkan field `products: Optional[List[Dict[str, Any]]] = None` (setelah `model_used`); default `None` sehingga absen dari JSON untuk klien lama/chat non-figure (Req 5.1).
      - Pastikan `from typing import List, Optional, Dict, Any` sudah ada di atas file (saat ini sudah: `from typing import List, Optional, Dict, Any`) — tidak perlu diubah bila lengkap.
      - Di awal `chat_with_ai`, setelah baris `today_str = datetime.now().strftime("%Y-%m-%d")`, tambahkan: `use_rag = True if request.use_rag is None else bool(request.use_rag)`.
      - Files: `backend/app/routes/chat.py`
      - Verify: dari folder `backend`, jalankan (cwd=backend) `python -c "from app.routes import chat; print('use_rag' in chat.ChatRequest.model_fields, 'products' in chat.ChatResponse.model_fields, hasattr(chat, 'chat_with_ai'))"` -> cetak `True True True` tanpa error import.
      - Manual (informatif): default ON dipilih agar demo menampilkan hasil ter-RAG lebih dulu dan klien lama tetap mendapat perilaku penuh (design §2).
      - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.6, 5.1_

- [x] 2. Filter `tools_schema` saat RAG OFF dan perluas `system_prompt` dengan blok rekomendasi figure.
      - Di `chat_with_ai`, tepat SETELAH blok `try/except` yang mengisi `tools_schema = mcp_tools_to_llm_schema(mcp_tools)` (dan fallback `tools_schema = []`), sisipkan filter: bila `not use_rag`, buang item dengan `function.name == 'search_figure_knowledge'` memakai `tools_schema = [t for t in tools_schema if t.get("function", {}).get("name") != "search_figure_knowledge"]`. Tool lain (`search_figures`, transaction, gatling) tetap utuh; bila `list_tools` gagal `tools_schema` sudah `[]` sehingga filter tidak berpengaruh (Req 2.5).
      - Setelah string `system_prompt` yang sudah ada selesai dibentuk (sebelum `messages = [{"role": "system", ...}]`), tambahkan `system_prompt += (...)` berisi blok "TOOL REKOMENDASI FIGURE ONE PIECE": jelaskan `search_figures` untuk PRODUK dan `search_figure_knowledge` untuk PENGETAHUAN (hanya bila RAG aktif); ATURAN A: untuk permintaan rekomendasi/pencarian figure panggil `search_figures`, dan bila `search_figure_knowledge` tersedia panggil JUGA lalu gabungkan keduanya; ATURAN B: jangan memanggil tool figure untuk pertanyaan keuangan/transaksi dan jangan mencampur tool keuangan dengan tool figure dalam satu jawaban. Jangan ubah aturan keuangan yang sudah ada.
      - Files: `backend/app/routes/chat.py`
      - Verify: dari folder `backend`, jalankan (cwd=backend) `python -c "from app.routes import chat; import inspect; src=inspect.getsource(chat.chat_with_ai); print('search_figure_knowledge' in src and 'TOOL REKOMENDASI FIGURE' in src)"` -> cetak `True` tanpa error import.
      - Manual (informatif): `tool_choice` tetap `auto` (sudah di `query_llm`); pengarahan dua tool murni via prompt (Req 3.2). Saat demo, bandingkan log `[BENCHMARK] ... tools=N`: OFF = N-1 (tanpa `search_figure_knowledge`).
      - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.5, 3.6_

- [x] 3. Early-return untuk figure tools di `sanitize_tool_args` sebelum injeksi `user_id`.
      - Di fungsi `sanitize_tool_args`, pada baris PERTAMA body (sebelum `args["user_id"] = user_id`) tambahkan: `if tool_name in ("search_figures", "search_figure_knowledge"): return args`. Ini memastikan figure tools diteruskan apa adanya tanpa `user_id` (schema figure tidak mendeklarasikan `user_id`).
      - Jangan ubah cabang transaksi mana pun (`create_transaction`, `get_transactions`, `update_transaction`, `delete_transaction`) — nol regresi untuk tool keuangan.
      - Files: `backend/app/routes/chat.py`
      - Verify: dari folder `backend`, jalankan (cwd=backend) `python -c "from app.routes import chat; a=chat.sanitize_tool_args('search_figures', {'query':'luffy'}, 7, 'rekomendasi luffy'); b=chat.sanitize_tool_args('search_figure_knowledge', {'query':'skala'}, 7, 'apa itu skala'); print('user_id' not in a, 'user_id' not in b, a=={'query':'luffy'})"` -> cetak `True True True`.
      - Manual (informatif): regresi ringkas tool transaksi — `sanitize_tool_args('delete_transaction', {'transaction_id':'3'}, 7, 'hapus')` tetap menyuntik `user_id` dan mem-parse id (design §5/Invarian).
      - _Requirements: 3.6_

- [x] 4. Gabungkan SEMUA `tool_outputs` ke sintesis dan ekstrak `products` dari hasil `search_figures`.
      - Di dalam blok `if tool_calls:`, inisialisasi `executed_tool_names = []` berdampingan dengan `tool_outputs = []`. Di akhir tiap iterasi loop (setelah `tool_outputs.append(...)`) tambahkan `executed_tool_names.append(fn_name)` sehingga paralel dengan `tool_outputs`.
      - Ganti pengiriman `tool_outputs[0]` ke sintesis: bentuk `combined_tool_output = "\n\n".join(f"[Hasil tool: {name}]\n{out}" for name, out in zip(executed_tool_names, tool_outputs))` dan pakai pada `content` user di `synthesis_messages`; perbarui `content` system sintesis agar bila ada hasil produk dan pengetahuan, keduanya digabungkan menjadi satu rekomendasi utuh (Req 3.4). Fallback sintesis gagal tetap `"\n\n".join(tool_outputs)` seperti sekarang.
      - Hapus/ganti blok peringatan `if len(tool_outputs) > 1: print(...)` karena perilakunya tidak lagi berlaku.
      - SETELAH loop eksekusi tool (saat `executed_tool_names`/`tool_outputs` lengkap, sebelum ronde sintesis), ekstrak products: inisialisasi `products = None`; loop `zip(executed_tool_names, tool_outputs)`, lewati yang bukan `search_figures`; untuk `search_figures` pertama `json.loads(out)`, ambil `results`, bila `isinstance(results, list)` set `products = results`; bungkus dengan `except (json.JSONDecodeError, TypeError, AttributeError): products = None`; `break` setelah `search_figures` pertama. `json` sudah di-import di atas file.
      - Sertakan `products=products` pada KEDUA return jalur sintesis: return sukses `ChatResponse(response=final_ai_msg, model_used=model_label, products=products)` dan return fallback `ChatResponse(response=fallback_ai_msg, model_used=model_label, products=products)`.
      - JANGAN rujuk `products` di return jalur lain (error LLM, jawab langsung, pengaman kosong) — biarkan default `None`. Pastikan `products` hanya didefinisikan di dalam blok `if tool_calls:` agar tidak ada `NameError` di jalur non-tool.
      - Files: `backend/app/routes/chat.py`
      - Verify: dari folder `backend`, jalankan (cwd=backend) `python -c "from app.routes import chat; import inspect; src=inspect.getsource(chat.chat_with_ai); print('executed_tool_names' in src, 'combined_tool_output' in src, 'products=products' in src, 'PERHATIAN' not in src)"` -> cetak `True True True True`. Dan import keseluruhan modul tidak error: `python -c "import app.routes.chat"`.
      - Manual (informatif): `results == []` (nol produk) -> `products = []`; frontend tidak merender kartu tapi teks `response` tetap tampil (Req 4.5). Hasil non-JSON/tanpa `results` -> `products = None`, request tetap sukses (Req 4.4). Chat keuangan/sapaan -> jalur non-tool -> `products=None` (Req 5.2); `save_chat_message` tetap di semua jalur (Req 5.3).
      - _Requirements: 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.2, 5.3, 5.4_

- [x] 5. Buat komponen `FigureProductCard.jsx` beserta util `formatIDR`.
      - Buat `frontend/src/components/FigureProductCard.jsx` sebagai komponen fungsi dengan props `figure` = satu objek `{id, nama, karakter, brand, skala, tinggi_cm, harga, stok, image_url, shopee_url}`.
      - Util `formatIDR(value)`: `const n = Number(value)`; bila `!Number.isFinite(n)` kembalikan `'Rp -'`; selain itu `new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(n)`.
      - State `const [imgFailed, setImgFailed] = useState(false)`. Bila `!imgFailed && figure.image_url`, render `<img src={figure.image_url} alt={figure.nama} onError={() => setImgFailed(true)} />`; selain itu render placeholder bertuliskan "Gambar tidak tersedia" tanpa merusak tata letak (tinggi sama).
      - Tampilkan `figure.nama`; baris `karakter/brand/skala` di-join dengan `' · '` memakai `[figure.karakter, figure.brand, figure.skala].filter(Boolean).join(' · ')`; harga via `formatIDR(figure.harga)`; stok via `const stok = Number(figure.stok) || 0` -> `stok > 0 ? 'Tersedia (' + stok + ')' : 'Habis'`; bila `figure.shopee_url`, link "Lihat di Shopee" dengan `href={figure.shopee_url} target="_blank" rel="noopener noreferrer"` dan `aria-label` jelas (mis. `Lihat ${figure.nama} di Shopee`).
      - Pakai kelas Tailwind sesuai contoh di design (kartu border/rounded, gambar `h-32 object-cover`, tombol Shopee oranye dengan `focus-visible:ring`). `export default FigureProductCard`.
      - Files: `frontend/src/components/FigureProductCard.jsx` (baru)
      - Verify: dari folder `frontend`, jalankan (cwd=frontend) `npm run build` -> SUKSES (komponen JSX valid; belum diimpor di mana pun sehingga build tetap hijau). JANGAN jalankan `npm run dev`.
      - _Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, NF3_

- [x] 6. Integrasikan `Chatbot.jsx`: state `useRag` + `products` per pesan, kirim `use_rag` khusus onepiece, render toggle RAG & kartu produk.
      - Di `frontend/src/components/Chatbot.jsx`, tambahkan `import FigureProductCard from './FigureProductCard';` di atas.
      - Di dalam komponen `Chatbot`, tambahkan `const isOnePiece = theme === 'onepiece';` dan `const [useRag, setUseRag] = useState(true);` (default ON, sinkron default backend).
      - Di `handleSend`, pada body `api.post('/chat/', {...})` sisipkan `...(isOnePiece ? { use_rag: useRag } : {})` setelah `model: selectedModel` sehingga tema fintracks tetap mengirim `{message, model}` saja. Saat menambah pesan AI ke `messages`, tambahkan field `products: isOnePiece ? (response.data.products || null) : null` pada objek pesan `{ role: 'ai', text, created_at, products }`.
      - Render RAG toggle HANYA bila `isOnePiece`, di area header (mis. di bawah Model Switcher Bar): tombol `role="switch"`, `aria-checked={useRag}`, teks `RAG: ON`/`RAG: OFF`, `onClick={() => setUseRag(v => !v)}`, `disabled={isLoading}`, dengan `focus-visible:ring` dan label jelas. Jangan render pada tema fintracks.
      - Render daftar kartu di bawah bubble AI HANYA bila `isOnePiece && Array.isArray(msg.products) && msg.products.length > 0`: `msg.products.map((fig) => <FigureProductCard key={fig.id ?? fig.nama} figure={fig} />)`. Bila products absen/kosong -> hanya teks `response`, seperti chat biasa.
      - Jangan ubah alur fintracks: tanpa toggle, tanpa kartu, body tetap `{message, model}`, model switcher/riwayat/CopyButton tetap sama.
      - Files: `frontend/src/components/Chatbot.jsx`
      - Verify: dari folder `frontend`, jalankan (cwd=frontend) `npm run build` -> SUKSES (import `FigureProductCard` valid, JSX valid). JANGAN jalankan `npm run dev`.
      - Manual (informatif): di `/anime` toggle RAG tampil dan mengubahnya mengirim `use_rag` sesuai status (cek Network tab); kartu produk render dari `response.data.products`. Dashboard fintracks: tanpa toggle/kartu, body request tetap `{message, model}`.
      - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.7, 7.8, 8.1, 8.2, 8.3, 8.4, NF2, NF3, NF4_

- [x] 7. Verifikasi integrasi backend + frontend.
      - Backend: dari folder `backend`, jalankan (cwd=backend) `python -c "import app.routes.chat as c; print('use_rag' in c.ChatRequest.model_fields, 'products' in c.ChatResponse.model_fields)"` -> `True True` tanpa error import.
      - Frontend: dari folder `frontend`, jalankan (cwd=frontend) `npm run build` -> SUKSES tanpa error.
      - Files: (tidak ada perubahan file; hanya menjalankan verifikasi)
      - Manual (informatif, fase implementasi): jalankan backend + MCP server + frontend; di `/anime` uji chat rekomendasi figure nyata memakai preset `gemini`/`gpt` — amati LLM memanggil `search_figures` (dan `search_figure_knowledge` saat RAG ON), kartu produk muncul, gambar rusak jatuh ke placeholder, link Shopee membuka tab baru. Bandingkan jawaban RAG ON vs OFF. Pastikan chatbot dashboard fintracks tidak berubah. Pengujian end-to-end ini adalah fase implementasi, bukan bagian task coding ini.
      - _Requirements: 1.4, 2.1, 3.1, 4.1, 5.4, 6.1, 7.1, 8.1, NF1, NF2_
