# Implementation Plan

Catatan: Fitur ini murni re-skin visual pada frontend (React 18 + Vite + React Router v6 + Tailwind). Backend tidak disentuh dan tidak ada dependency baru. Aset gambar `frontend/src/assets/den-den-mushi.jpg` sudah tersedia (diimpor dengan ekstensi `.jpg`). Setiap task menjaga codebase tetap bisa di-build.

- [x] 1. Buat Chatbot theme-able lewat prop `theme` + objek `THEMES`
      - Ubah tanda tangan komponen di `frontend/src/components/Chatbot.jsx` dari `const Chatbot = () => {` menjadi `const Chatbot = ({ theme = 'fintracks' }) => {` sehingga prop `theme` opsional dengan default `'fintracks'`.
      - Tambahkan `import dendenMushi from '../assets/den-den-mushi.jpg';` di bagian import atas file (ekstensi `.jpg`, bukan `.png`, karena itu berkas nyata yang ada).
      - Di luar komponen (sejajar dengan helper `copyToClipboard`/`formatChatTime`), tambahkan objek konfigurasi `THEMES` persis seperti design: `fintracks` → `{ title: 'FinTracks AI', headerClass: 'bg-blue-600', avatar: { type: 'emoji', value: '🤖' } }`; `onepiece` → `{ title: 'AI Assistant', headerClass: 'bg-gradient-to-r from-red-700 to-amber-600', avatar: { type: 'image', src: dendenMushi, alt: 'Den Den Mushi', fallback: '🐌' } }`.
      - Di dalam komponen, resolusikan tema: `const activeTheme = THEMES[theme] || THEMES.fintracks;` agar nilai tak dikenal/`undefined` jatuh ke `fintracks` tanpa crash.
      - Cabangkan HANYA 3 titik presentasi di header: (a) ganti `bg-blue-600` pada div header menjadi template string `` className={`${activeTheme.headerClass} p-3.5 text-white flex flex-col gap-2 shadow`} ``; (b) ganti teks hardcoded `FinTracks AI` menjadi `{activeTheme.title}`; (c) tambahkan elemen avatar kecil di sebelah kiri judul (di dalam `div.flex.items-center.gap-2` yang berisi dot hijau + judul).
      - Render avatar: jika `activeTheme.avatar.type === 'image'` render `<img src={activeTheme.avatar.src} alt={activeTheme.avatar.alt} className="w-6 h-6 rounded-full object-cover bg-white/20" onError={...}/>` dengan fallback ke emoji saat gagal muat; jika tidak, render `<span className="text-lg">{activeTheme.avatar.value}</span>`. Gunakan pendekatan `useState` lokal `avatarFailed` (di-set `true` pada `onError`, lalu render emoji fallback `activeTheme.avatar.fallback` saat `true`) agar konsisten gaya React komponen ini.
      - JANGAN ubah apa pun selain 3 titik presentasi di atas: seluruh `state` (`messages`, `input`, `isLoading`, `isFetchingHistory`, `selectedModel`, `modelOptions`), kedua `useEffect` (fetch `/chat/history` dan `/chat/models`), `handleSend` (POST `/chat/`), `handleModelChange`, `handleClearHistory`, dropdown pemilih model, tombol "Hapus Chat", `CopyButton`, area pesan, form input, dan class container utama (`fixed bottom-24 right-6 w-96 h-[520px] ...`) tetap identik.
      - Files: `frontend/src/components/Chatbot.jsx`
      - Verify: dari folder `frontend` jalankan `npm run build` dan pastikan build sukses (import `.jpg` tidak memecah bundle, tidak ada error kompilasi/JSX).
      - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 8.1, 8.2, 8.3_

- [x] 2. Buat halaman bertema One Piece `OnePiece.jsx`
      - Buat `frontend/src/pages/OnePiece.jsx` sebagai komponen fungsional React mengikuti pola halaman existing (`GatlingDashboard.jsx`, `Dashboard.jsx`).
      - Gunakan container bertema visual One Piece, misalnya `className="min-h-screen bg-gradient-to-b from-sky-700 via-sky-500 to-amber-200"` (nuansa laut ke pasir).
      - Tambahkan header dengan judul (mis. `<h1 className="text-3xl font-bold text-white drop-shadow">One Piece</h1>`) dan tombol "← Kembali ke Dashboard" yang memanggil `navigate('/dashboard')` menggunakan `useNavigate` dari `react-router-dom`.
      - Isi area konten dengan dekorasi/banner bertema One Piece (re-skin visual saja, tanpa logika baru).
      - JANGAN me-render `<Chatbot />` di dalam `OnePiece.jsx` — Chatbot akan dirender oleh `OnePieceLayout` (task 3) agar tepat satu instance pada route `/anime`.
      - Files: `frontend/src/pages/OnePiece.jsx`
      - Verify: dari folder `frontend` jalankan `npm run build` dan pastikan modul baru ini ikut ter-compile tanpa error.
      - _Requirements: 3.1, 3.2, 3.3_

- [x] 3. Tambahkan `OnePieceLayout` + route terproteksi `/anime` di `App.jsx`
      - Di `frontend/src/App.jsx` tambahkan `import OnePiece from './pages/OnePiece';` dan `import dendenMushi from './assets/den-den-mushi.jpg';`.
      - Buat komponen `OnePieceLayout` yang meniru pola `DashboardLayout` existing: `const [showChatbot, setShowChatbot] = useState(false);`, render `<OnePiece />`, lalu `{showChatbot && <Chatbot theme="onepiece" />}`.
      - Tambahkan floating toggle button `fixed bottom-6 right-6` bertema merah (mis. `bg-red-700 hover:bg-red-800`) berukuran 60x60 yang men-toggle `showChatbot`; isinya `<img src={dendenMushi} alt="Den Den Mushi" className="w-8 h-8 object-cover rounded-full" onError={...}/>` dengan fallback ke emoji `🐌` bila gambar gagal dimuat.
      - Tambahkan route baru di dalam `<Routes>`: `<Route path="/anime" element={<ProtectedRoute><OnePieceLayout /></ProtectedRoute>} />` menggunakan `ProtectedRoute` yang sudah ada (menangani loading/redirect ke `/login`/render untuk pengguna terautentikasi).
      - JANGAN ubah `DashboardLayout` — tetap me-render `<Chatbot />` tanpa prop (tema default `fintracks`) dengan ikon toggle emoji 🤖.
      - Files: `frontend/src/App.jsx`
      - Verify: dari folder `frontend` jalankan `npm run build` dan pastikan sukses; route serta import baru tidak menimbulkan error.
      - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.2, 3.3, 7.1, 7.2, 7.3, 7.4, 7.5, 6.1, 6.2, 6.3_

- [x] 4. Tambahkan tombol "Anime" di header Dashboard
      - Di `frontend/src/pages/Dashboard.jsx`, di dalam `div className="flex gap-3 items-center"`, tambahkan sebuah `<button>` sebagai anak PERTAMA — tepat sebelum tombol "Gatling Studio" — tanpa elemen interaktif lain di antara keduanya.
      - Tombol memanggil `onClick={() => navigate('/anime')}` (hook `useNavigate` sudah tersedia di komponen).
      - Beri gaya bertema One Piece merah/emas (mis. `className="bg-gradient-to-r from-red-600 to-amber-500 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:from-red-700 hover:to-amber-600 transition-all shadow-sm flex items-center gap-2"`).
      - Label teks tombol HARUS persis `Anime`. Ikon bendera bajak laut `🏴‍☠️` boleh ditambahkan sebagai dekorasi (mis. `<span>🏴‍☠️</span> Anime`) tetapi tidak mengubah label teks.
      - Files: `frontend/src/pages/Dashboard.jsx`
      - Verify: dari folder `frontend` jalankan `npm run build` dan pastikan sukses tanpa error.
      - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 5. Verifikasi integrasi end-to-end (build + dev) seluruh fitur
      - Pastikan keempat task sebelumnya terintegrasi: pastikan tidak ada import yang pecah dan hanya ada satu instance `Chatbot` pada route `/anime` (dirender oleh `OnePieceLayout`, bukan oleh `OnePiece.jsx`).
      - Verify (build): dari folder `frontend` jalankan `npm run build` — build Vite harus sukses (import aset `.jpg` tidak memecah bundle, tidak ada error).
      - Verify (dev): dari folder `frontend` jalankan `npm run dev`, lalu cek manual di browser:
        - Tombol "Anime" muncul di header Dashboard tepat di kiri "Gatling Studio" dengan label persis "Anime".
        - Klik "Anime" → redirect ke `/anime` dan halaman bertema One Piece tampil.
        - Di `/anime`, toggle button mengambang (ikon Den Den Mushi) memunculkan Chatbot dengan avatar Den Den Mushi dan nama "AI Assistant".
        - Chatbot di `/anime` masih bisa kirim/terima pesan (POST `/chat/`), riwayat, pemilih model, salin pesan, dan penanganan error berfungsi identik.
        - Kembali ke Dashboard: chatbot biasa TIDAK berubah (judul "FinTracks AI", header biru `bg-blue-600`, avatar 🤖, ikon toggle 🤖).
        - (Opsional) Uji fallback: sementara ganti nama berkas `den-den-mushi.jpg` → avatar dan ikon toggle menampilkan emoji 🐌, UI tetap jalan; kembalikan nama berkas setelahnya.
        - (Opsional) Uji proteksi: logout lalu akses `/anime` langsung → redirect ke `/login`.
      - Files: tidak ada perubahan kode baru pada task ini (verifikasi saja).
      - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3_
