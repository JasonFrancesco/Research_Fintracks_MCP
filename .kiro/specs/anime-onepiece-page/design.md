# Technical Design: anime-onepiece-page

## Overview

Fitur ini menambahkan halaman baru bertema visual One Piece (`OnePiece_Page`) yang dapat diakses pengguna login melalui tombol "Anime" di header Dashboard. Halaman tersebut menampilkan ulang komponen `Chatbot` yang sudah ada — tanpa duplikasi — dengan menjadikannya theme-able lewat satu prop baru `theme`. Hanya bagian presentasi (judul, warna header, avatar) yang bercabang berdasarkan `theme`; seluruh logika chat (riwayat, pemilih model, salin pesan, penanganan error, pemanggilan backend) tetap identik dan tidak disentuh.

Desain ini murni **re-skin visual pada sisi frontend**. Tidak ada perubahan backend, tidak ada state management/context baru, dan tidak ada dependency npm baru. Stack yang dipakai terkunci: **React 18 + Vite + React Router v6 + Tailwind CSS** (semua sudah ada di `frontend/`).

Bagaimana desain memenuhi requirements secara ringkas:
- Tombol "Anime" di header Dashboard, di kiri "Gatling Studio" → Req 1.
- Route baru `/anime` dibungkus `ProtectedRoute` → Req 2.
- Halaman `OnePiece.jsx` bertema One Piece yang me-render satu `Chatbot` dengan `theme="onepiece"` → Req 3.
- Prop `theme` pada `Chatbot` dengan default `"fintracks"` dan objek konfigurasi tema, logika chat tidak berubah → Req 4.
- Tema `"onepiece"` hanya mengubah avatar (gambar Den Den Mushi) + nama "AI Assistant", dengan fallback bila gambar gagal dimuat → Req 5 & 8.
- Tema `"fintracks"` tetap seperti semula (header biru, "FinTracks AI", 🤖) → Req 6.
- Tombol toggle di `OnePieceLayout` memakai ikon Den Den Mushi (dengan fallback); Dashboard tetap 🤖 → Req 7.

## Catatan Penting tentang Aset Gambar

Requirements dan prompt menyebut path `frontend/src/assets/den-den-mushi.png`. Hasil investigasi codebase: file yang sebenarnya tersedia adalah **`frontend/src/assets/den-den-mushi.jpg`** (ekstensi `.jpg`, bukan `.png`). Desain ini memakai file nyata `den-den-mushi.jpg` agar implementasi tidak gagal saat build Vite. Ini tidak mengubah substansi Req 8 (gambar dirujuk dari `frontend/src/assets/`), hanya menyesuaikan ekstensi ke berkas yang benar-benar ada. Jika nanti pengguna mengganti ke `.png`, cukup ubah satu baris `import`.

## Arsitektur: File yang Diubah vs Dibuat Baru

### Dibuat baru
- **`frontend/src/pages/OnePiece.jsx`** — Komponen halaman bertema One Piece. Me-render konten bertema + satu `<Chatbot theme="onepiece" />`. Mengikuti pola halaman yang sudah ada (`GatlingDashboard.jsx`, `GatlingCopilot.jsx`).

### Diubah
- **`frontend/src/App.jsx`** — (a) tambah `import OnePiece`; (b) tambah komponen layout `OnePieceLayout` yang meniru `DashboardLayout` (toggle button + `<Chatbot theme="onepiece" />`); (c) tambah satu `<Route path="/anime" ... />` yang dibungkus `ProtectedRoute`.
- **`frontend/src/pages/Dashboard.jsx`** — tambah tombol "Anime" di dalam `div.flex.gap-3.items-center`, diletakkan **sebelum** tombol "Gatling Studio".
- **`frontend/src/components/Chatbot.jsx`** — tambah prop `theme` (default `'fintracks'`) + objek konfigurasi `THEMES`, lalu cabangkan hanya bagian presentasi (judul, `className` header, avatar). Logika dan struktur fungsional tidak diubah.

Tidak ada file lain yang disentuh. Tidak ada perubahan di `backend/` atau `mcp-server/`.

## Desain Komponen

### 1. `Chatbot.jsx` — prop `theme` + konfigurasi tema

Tanda tangan komponen berubah dari tanpa-props menjadi menerima satu prop opsional `theme`:

```jsx
const Chatbot = ({ theme = 'fintracks' }) => { ... }
```

Di bagian atas file (di luar komponen, sejajar dengan helper yang sudah ada), tambahkan import aset dan objek konfigurasi tema:

```jsx
import dendenMushi from '../assets/den-den-mushi.jpg';

// Konfigurasi presentasi per tema. Hanya memengaruhi tampilan header & avatar;
// seluruh logika chat tetap sama untuk semua tema.
const THEMES = {
    fintracks: {
        title: 'FinTracks AI',
        headerClass: 'bg-blue-600',          // warna header default (biru)
        avatar: { type: 'emoji', value: '🤖' },
    },
    onepiece: {
        title: 'AI Assistant',
        headerClass: 'bg-gradient-to-r from-red-700 to-amber-600', // nuansa One Piece merah/emas
        avatar: { type: 'image', src: dendenMushi, alt: 'Den Den Mushi', fallback: '🐌' },
    },
};
```

Resolusi tema (menangani nilai tidak dikenal → fallback ke `fintracks`, memenuhi Req 4.4):

```jsx
const activeTheme = THEMES[theme] || THEMES.fintracks;
```

**Render avatar** di header. Saat ini header hanya menampilkan dot hijau `animate-pulse` + `<span className="font-bold text-sm">FinTracks AI</span>`. Perubahan:
- Ganti teks judul hardcoded `FinTracks AI` menjadi `{activeTheme.title}`.
- Ganti `bg-blue-600` pada div header menjadi `{activeTheme.headerClass}` (dengan string template agar kelas lain tetap). Contoh: `className={\`${activeTheme.headerClass} p-3.5 text-white flex flex-col gap-2 shadow\`}`.
- Tambahkan elemen avatar kecil di sebelah kiri judul.

Pola render avatar (emoji vs gambar dengan fallback `onError`):

```jsx
{activeTheme.avatar.type === 'image' ? (
    <img
        src={activeTheme.avatar.src}
        alt={activeTheme.avatar.alt}
        className="w-6 h-6 rounded-full object-cover bg-white/20"
        onError={(e) => {
            // Req 5.4 & 8.3: gambar gagal dimuat → ganti ke fallback teks/emoji, UI tetap jalan.
            e.currentTarget.onerror = null;              // cegah loop
            e.currentTarget.replaceWith(
                Object.assign(document.createElement('span'), {
                    className: 'text-lg',
                    textContent: activeTheme.avatar.fallback,
                })
            );
        }}
    />
) : (
    <span className="text-lg">{activeTheme.avatar.value}</span>
)}
```

Catatan implementasi: bila implementer lebih suka pendekatan React murni untuk fallback (tanpa manipulasi DOM langsung), boleh menambah satu `useState` lokal `avatarFailed` yang di-set `true` pada `onError`, lalu merender emoji fallback saat `avatarFailed === true`. Keduanya sah; yang penting ada fallback dan UI tidak berhenti. Pilih pendekatan `useState` jika ingin konsisten dengan gaya React komponen ini.

**Yang TIDAK berubah** (wajib, Req 4.5–4.9, Req 5.3, Req 6): seluruh `state` (`messages`, `input`, `isLoading`, `isFetchingHistory`, `selectedModel`, `modelOptions`), kedua `useEffect` (fetch `/chat/history` dan `/chat/models`), `handleSend` (POST `/chat/`), `handleModelChange`, `handleClearHistory`, dropdown pemilih model, tombol "Hapus Chat", komponen `CopyButton`, area pesan, form input, serta seluruh class container utama (`fixed bottom-24 right-6 w-96 h-[520px] ...`). Hanya 3 titik presentasi di header yang bercabang: judul, warna header, avatar.

### 2. `OnePiece.jsx` — halaman bertema

Komponen halaman sederhana yang menampilkan tema visual One Piece dan meneruskan `theme="onepiece"` ke `Chatbot`. Mengikuti pola halaman existing (fungsional, pakai `useNavigate` bila perlu tombol kembali). Chatbot tidak di-render langsung di halaman ini melainkan oleh `OnePieceLayout` (lihat Routing) agar pola toggle button identik dengan `DashboardLayout`. `OnePiece.jsx` fokus pada konten bertema.

Struktur ringkas:

```jsx
import React from 'react';
import { useNavigate } from 'react-router-dom';

const OnePiece = () => {
    const navigate = useNavigate();
    return (
        <div className="min-h-screen bg-gradient-to-b from-sky-700 via-sky-500 to-amber-200">
            <header className="flex items-center justify-between p-6">
                <h1 className="text-3xl font-bold text-white drop-shadow">One Piece</h1>
                <button
                    onClick={() => navigate('/dashboard')}
                    className="bg-white/90 text-red-700 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-white transition"
                >
                    ← Kembali ke Dashboard
                </button>
            </header>
            {/* Konten bertema One Piece (hero / banner / dekorasi). Re-skin visual saja. */}
        </div>
    );
};

export default OnePiece;
```

Pembagian tanggung jawab (Req 3.2 "tepat satu instance Chatbot"): `Chatbot` di-render oleh `OnePieceLayout`, bukan di dalam `OnePiece.jsx`. Dengan begitu hanya ada satu instance pada route `/anime`.

### 3. `App.jsx` — `OnePieceLayout` + route

`OnePieceLayout` meniru persis pola `DashboardLayout` yang sudah ada: `useState showChatbot`, render halaman + `Chatbot` saat toggle aktif, dan floating toggle button di kanan bawah. Perbedaannya: me-render `<OnePiece />`, meneruskan `theme="onepiece"` ke `Chatbot`, dan ikon toggle memakai gambar Den Den Mushi (bukan emoji 🤖).

```jsx
import OnePiece from './pages/OnePiece';
import dendenMushi from './assets/den-den-mushi.jpg';

const OnePieceLayout = () => {
    const [showChatbot, setShowChatbot] = useState(false);
    return (
        <div className="relative">
            <OnePiece />
            {showChatbot && <Chatbot theme="onepiece" />}
            <button
                onClick={() => setShowChatbot(!showChatbot)}
                className="fixed bottom-6 right-6 bg-red-700 text-white p-4 rounded-full shadow-2xl hover:bg-red-800 transition-all z-50 flex items-center justify-center hover:scale-105 active:scale-95 overflow-hidden"
                style={{ width: '60px', height: '60px' }}
                title="One Piece AI Assistant"
            >
                <img
                    src={dendenMushi}
                    alt="Den Den Mushi"
                    className="w-8 h-8 object-cover rounded-full"
                    onError={(e) => {              // Req 7.5: fallback bila gambar gagal
                        e.currentTarget.onerror = null;
                        e.currentTarget.replaceWith(
                            Object.assign(document.createElement('span'), {
                                className: 'text-2xl',
                                textContent: '🐌',
                            })
                        );
                    }}
                />
            </button>
        </div>
    );
};
```

Route baru (ditempatkan bersama route lain di dalam `<Routes>`):

```jsx
<Route
    path="/anime"
    element={
        <ProtectedRoute>
            <OnePieceLayout />
        </ProtectedRoute>
    }
/>
```

`ProtectedRoute` yang sudah ada menangani Req 2.2–2.5 tanpa perubahan: saat `loading` menampilkan indikator "Loading FinTracks...", saat tidak ada `user` redirect ke `/login`, saat ada `user` me-render children.

### 4. `Dashboard.jsx` — tombol "Anime"

Tombol "Anime" ditambahkan sebagai anak **pertama** di dalam `div className="flex gap-3 items-center"`, sehingga muncul di sebelah kiri tombol "Gatling Studio" (Req 1.2). Mengikuti gaya tombol lain, memakai tema warna One Piece (merah/emas). Handler memakai `navigate('/anime')` (hook `useNavigate` sudah tersedia di `Dashboard`).

```jsx
<div className="flex gap-3 items-center">
    {/* TOMBOL BARU — diletakkan sebelum Gatling Studio */}
    <button
        onClick={() => navigate('/anime')}
        className="bg-gradient-to-r from-red-600 to-amber-500 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:from-red-700 hover:to-amber-600 transition-all shadow-sm flex items-center gap-2"
    >
        <span>🏴‍☠️</span> Anime
    </button>

    <button onClick={() => navigate('/gatling')} className="bg-gradient-to-r from-orange-500 to-amber-600 ...">
        <span>⚡</span> Gatling Studio
    </button>
    {/* ...tombol AI Copilot, + Tambah Transaksi, Logout tetap ... */}
</div>
```

Label teks tombol harus persis `Anime` (Req 1.3). Ikon bendera bajak laut bersifat dekoratif dan tidak mengubah label teks.

## Penanganan Aset Gambar & Fallback

- **Import via Vite**: gambar diimpor sebagai modul (`import dendenMushi from '../assets/den-den-mushi.jpg'`). Vite mengubahnya menjadi URL ter-hash saat build. Dipakai di dua tempat: avatar header `Chatbot` (tema onepiece) dan ikon toggle di `OnePieceLayout`.
- **Fallback (`onError`)**: setiap `<img>` Den Den Mushi memiliki handler `onError` yang mengganti gambar dengan emoji siput `🐌` (atau teks alternatif) sehingga UI tidak berhenti bila berkas hilang/corrupt. Ini memenuhi Req 5.4, Req 7.5, dan Req 8.3.
- **Lokasi berkas**: `frontend/src/assets/den-den-mushi.jpg`. Folder `assets/` sudah ada dan berkas sudah disediakan pengguna (prasyarat Req 8).

## Validasi Input & Invariant

Fitur ini tidak menerima input eksternal baru dari pengguna (tidak ada form/parameter baru). Satu-satunya "input tidak tepercaya" dari sudut pandang komponen adalah **nilai prop `theme`** dan **ketersediaan berkas gambar**:

- `theme`: opsional, tipe string, nilai yang didukung `'fintracks'` | `'onepiece'`. Perilaku pada kegagalan: nilai tidak diberikan → default `'fintracks'` (Req 4.2); nilai tidak dikenal → fallback ke `'fintracks'` dan tetap render (Req 4.4). Enforcement dipegang di layer komponen `Chatbot` lewat ekspresi `THEMES[theme] || THEMES.fintracks`, karena komponenlah yang memiliki pengetahuan tentang set tema valid.
- Gambar Den Den Mushi: enforcement fallback dipegang di layer elemen `<img>` (handler `onError`) di masing-masing titik render (header `Chatbot` dan toggle `OnePieceLayout`), karena kegagalan load hanya diketahui di runtime per elemen.

Invariant "hanya satu instance `Chatbot` pada `/anime`" dipegang oleh `OnePieceLayout` (satu-satunya yang me-render `Chatbot`), bukan oleh `OnePiece.jsx`.

## Edge Cases

- **Berkas gambar hilang/rusak** → `onError` menampilkan emoji fallback, baik di avatar maupun di tombol toggle.
- **Prop `theme` salah ketik / `undefined`** → jatuh ke tema `fintracks`, tidak crash.
- **Pengguna belum login mengakses `/anime` langsung** → `ProtectedRoute` redirect ke `/login`.
- **Status auth masih loading** → `ProtectedRoute` menampilkan indikator loading, belum render/redirect.
- **Toggle chatbot** → state `showChatbot` lokal per layout; membuka/menutup tidak memengaruhi Dashboard dan sebaliknya.
- **Dashboard default tidak berubah** → `DashboardLayout` tetap me-render `<Chatbot />` tanpa prop, sehingga `theme` default `fintracks` (header biru, "FinTracks AI", 🤖).

## Pemetaan ke Requirements

| Requirement | Dipenuhi oleh bagian desain |
|---|---|
| Req 1 (Tombol Anime di header) | `Dashboard.jsx` — tombol "Anime" sebagai anak pertama `div.flex.gap-3.items-center`, label persis "Anime", `onClick navigate('/anime')` |
| Req 2 (Routing terproteksi) | `App.jsx` — `<Route path="/anime">` dibungkus `ProtectedRoute` (existing menangani loading/redirect/render) |
| Req 3 (Tampilan halaman One Piece) | `OnePiece.jsx` bertema One Piece; `OnePieceLayout` me-render tepat satu `<Chatbot theme="onepiece" />` |
| Req 4 (Chatbot theme-able) | `Chatbot.jsx` — prop `theme` default `'fintracks'`, objek `THEMES`, fallback `THEMES[theme] || THEMES.fintracks`; logika chat tidak diubah |
| Req 5 (Tampilan chatbot onepiece) | `THEMES.onepiece` → avatar gambar Den Den Mushi + judul "AI Assistant"; `onError` fallback; elemen fungsional lain tidak berubah |
| Req 6 (Tema default tidak berubah) | `THEMES.fintracks` → "FinTracks AI", `bg-blue-600`, emoji 🤖; `DashboardLayout` memanggil `<Chatbot />` tanpa prop |
| Req 7 (Ikon toggle onepiece) | `OnePieceLayout` toggle pakai `<img>` Den Den Mushi + `onError` fallback; `DashboardLayout` tetap 🤖; `showChatbot` menangani show/hide |
| Req 8 (Prasyarat gambar) | Import dari `frontend/src/assets/den-den-mushi.jpg` (berkas nyata); fallback bila tidak tersedia |

## Strategi Verifikasi / Testing Manual

Fitur ini re-skin visual tanpa logika baru, jadi verifikasi utama adalah manual/visual. Unit test otomatis tidak wajib untuk scope ini; jika diinginkan, yang paling layak di-unit-test adalah resolusi `THEMES[theme] || THEMES.fintracks` (pemetaan prop → judul/avatar). Interaksi routing + toggle + pemanggilan backend lebih tepat diverifikasi secara integrasi/manual.

Langkah verifikasi manual (jalankan dari folder `frontend`, `npm run dev` — **tidak dijalankan pada langkah pembuatan design ini**, hanya didokumentasikan):

1. Login ke aplikasi, buka Dashboard. Pastikan tombol **"Anime"** muncul di header, tepat **di sebelah kiri "Gatling Studio"**, dengan label persis "Anime".
2. Klik tombol "Anime" → aplikasi redirect ke `/anime` dan menampilkan halaman bertema One Piece.
3. Pada `/anime`, klik tombol toggle mengambang di kanan bawah → `Chatbot` muncul dengan **avatar Den Den Mushi** dan nama **"AI Assistant"**; ikon tombol toggle juga memakai gambar Den Den Mushi.
4. Kirim pesan di chatbot `/anime` → pesan terkirim dan balasan diterima seperti biasa (POST `/chat/`), riwayat, pemilih model, salin pesan, dan penanganan error berfungsi identik.
5. Kembali ke Dashboard, buka chatbot biasa → pastikan **tidak berubah**: judul "FinTracks AI", header biru (`bg-blue-600`), avatar emoji robot 🤖, ikon toggle 🤖.
6. Uji fallback gambar: sementara ganti nama berkas `den-den-mushi.jpg` → avatar dan ikon toggle menampilkan emoji fallback 🐌, UI tetap berjalan. Kembalikan nama berkas setelah uji.
7. Uji proteksi route: logout, akses `/anime` langsung → redirect ke `/login`.

Catatan: jalankan build/dev server pada tahap implementasi, bukan pada tahap pembuatan design ini.
