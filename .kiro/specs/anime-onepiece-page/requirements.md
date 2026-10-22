# Requirements Document

## Introduction

Fitur "anime-onepiece-page" menambahkan sebuah halaman baru bertema visual One Piece ke aplikasi FinTracks. Pengguna yang sudah login dapat mengakses halaman ini melalui tombol "Anime" yang baru di header Dashboard. Halaman One Piece menampilkan ulang komponen chatbot yang sudah ada (tanpa menduplikasi komponen) menggunakan prop `theme`, di mana tema "onepiece" hanya mengubah tampilan avatar/foto profil chatbot menjadi gambar Den Den Mushi. Fitur ini murni re-skin visual pada sisi frontend: logika dan perilaku chatbot (riwayat, pemilih model, salin pesan, penanganan error, pemanggilan backend) tidak berubah, dan chatbot FinTracks default tidak terpengaruh sama sekali. Backend tidak diubah untuk fitur ini.

## Glossary

- **FinTracks_App**: Aplikasi web FinTracks berbasis React yang berjalan di sisi frontend (`frontend/src/`).
- **Dashboard_Header**: Area header pada halaman Dashboard (`frontend/src/pages/Dashboard.jsx`), yaitu div dengan className `flex gap-3 items-center` yang memuat tombol "Gatling Studio".
- **Anime_Button**: Tombol baru berlabel "Anime" yang ditempatkan di Dashboard_Header.
- **Gatling_Button**: Tombol "Gatling Studio" yang sudah ada di Dashboard_Header.
- **OnePiece_Page**: Halaman baru bertema visual One Piece yang menjadi tujuan navigasi dari Anime_Button.
- **Router**: Mekanisme routing React Router v6 yang dikonfigurasi di `frontend/src/App.jsx`.
- **ProtectedRoute**: Pembungkus route yang sudah ada yang hanya mengizinkan akses bagi pengguna terautentikasi dan mengarahkan pengguna yang belum login ke `/login`.
- **Chatbot_Component**: Komponen chatbot tunggal yang sudah ada (`frontend/src/components/Chatbot.jsx`), yang akan dibuat theme-able melalui prop `theme`.
- **Theme_Prop**: Prop bernama `theme` pada Chatbot_Component dengan nilai "fintracks" (default) atau "onepiece".
- **DenDenMushi_Image**: File gambar Den Den Mushi yang disediakan pengguna, disimpan di `frontend/src/assets/den-den-mushi.png`.
- **Chatbot_Toggle_Button**: Tombol mengambang (floating button) di kanan bawah yang menampilkan atau menyembunyikan Chatbot_Component.
- **Default_Theme**: Nilai Theme_Prop "fintracks", yaitu tampilan chatbot bawaan (header biru, judul "FinTracks AI", avatar emoji robot 🤖).
- **OnePiece_Theme**: Nilai Theme_Prop "onepiece", yaitu tampilan chatbot dengan avatar DenDenMushi_Image dan judul "AI Assistant".

## Requirements

### Requirement 1: Tombol Anime di Header Dashboard

**User Story:** Sebagai pengguna FinTracks yang sudah login, saya ingin melihat tombol "Anime" di header Dashboard, agar saya dapat membuka halaman bertema One Piece.

#### Acceptance Criteria

1. WHILE pengguna sudah login dan Dashboard_Header ditampilkan, THE FinTracks_App SHALL menampilkan Anime_Button di dalam Dashboard_Header.
2. THE FinTracks_App SHALL menempatkan Anime_Button langsung di sebelah kiri Gatling_Button di dalam Dashboard_Header, tanpa elemen interaktif lain di antara keduanya.
3. THE Anime_Button SHALL menampilkan label teks persis "Anime".
4. WHEN pengguna mengeklik Anime_Button, THE FinTracks_App SHALL menavigasikan pengguna ke OnePiece_Page.

### Requirement 2: Routing ke Halaman One Piece untuk Pengguna Terautentikasi

**User Story:** Sebagai pengguna FinTracks yang sudah login, saya ingin halaman One Piece dapat diakses melalui sebuah route khusus, agar halaman tersebut hanya terbuka bagi pengguna yang berhak.

#### Acceptance Criteria

1. THE Router SHALL mendefinisikan satu route baru dengan path unik yang me-render OnePiece_Page.
2. THE Router SHALL membungkus route OnePiece_Page dengan ProtectedRoute sehingga akses dievaluasi sebelum OnePiece_Page dirender.
3. WHEN pengguna yang belum terautentikasi mengakses route OnePiece_Page, THE ProtectedRoute SHALL mengarahkan pengguna ke `/login` dan tidak me-render OnePiece_Page.
4. WHILE pengguna terautentikasi, THE Router SHALL me-render OnePiece_Page saat route OnePiece_Page diakses.
5. WHILE status autentikasi masih dalam proses pemeriksaan (loading), THE ProtectedRoute SHALL menampilkan indikator loading dan belum me-render OnePiece_Page maupun redirect.

### Requirement 3: Tampilan Visual Halaman One Piece

**User Story:** Sebagai pengguna FinTracks, saya ingin halaman One Piece menampilkan tema visual One Piece, agar saya mendapatkan pengalaman bertema anime yang berbeda dari Dashboard biasa.

#### Acceptance Criteria

1. WHEN pengguna membuka OnePiece_Page, THE OnePiece_Page SHALL menampilkan konten dengan tema visual One Piece.
2. THE OnePiece_Page SHALL me-render tepat satu instance Chatbot_Component.
3. THE OnePiece_Page SHALL meneruskan nilai "onepiece" ke Theme_Prop pada Chatbot_Component.

### Requirement 4: Chatbot Theme-able melalui Prop Theme

**User Story:** Sebagai pengembang, saya ingin satu komponen Chatbot yang dapat diubah temanya melalui prop, agar tidak ada duplikasi komponen chatbot dan logika chat tetap terpusat.

#### Acceptance Criteria

1. THE Chatbot_Component SHALL menerima Theme_Prop dengan tepat dua nilai yang didukung: "fintracks" dan "onepiece".
2. WHERE Theme_Prop tidak diberikan, THE Chatbot_Component SHALL menggunakan "fintracks" sebagai nilai default.
3. WHEN Chatbot_Component dirender, THE Chatbot_Component SHALL menerapkan gaya visual yang sesuai dengan nilai Theme_Prop.
4. IF Theme_Prop bernilai tidak dikenal, THEN THE Chatbot_Component SHALL menggunakan tampilan default "fintracks" dan tetap merender tanpa berhenti.
5. THE Chatbot_Component SHALL mempertahankan perilaku riwayat percakapan yang identik untuk kedua nilai Theme_Prop.
6. THE Chatbot_Component SHALL mempertahankan perilaku pemilih model yang identik untuk kedua nilai Theme_Prop.
7. THE Chatbot_Component SHALL mempertahankan fungsi salin pesan yang identik untuk kedua nilai Theme_Prop.
8. THE Chatbot_Component SHALL mempertahankan penanganan error yang identik untuk kedua nilai Theme_Prop.
9. THE Chatbot_Component SHALL memanggil endpoint `/chat/`, `/chat/history`, dan `/chat/models` dengan urutan dan parameter yang identik untuk kedua nilai Theme_Prop.

### Requirement 5: Tampilan Chatbot pada Tema One Piece

**User Story:** Sebagai pengguna di halaman One Piece, saya ingin avatar chatbot menampilkan gambar Den Den Mushi dengan nama "AI Assistant", agar chatbot terasa sesuai tema One Piece.

#### Acceptance Criteria

1. WHERE Theme_Prop bernilai "onepiece", WHEN Chatbot_Component dirender, THE Chatbot_Component SHALL menampilkan DenDenMushi_Image sebagai avatar chatbot.
2. WHERE Theme_Prop bernilai "onepiece", WHEN Chatbot_Component dirender, THE Chatbot_Component SHALL menampilkan nama chatbot persis "AI Assistant".
3. WHERE Theme_Prop bernilai "onepiece", THE Chatbot_Component SHALL mengubah hanya avatar dan nama chatbot dibandingkan Default_Theme, serta mempertahankan seluruh elemen fungsional dan tata letak lainnya.
4. IF DenDenMushi_Image gagal dimuat saat Theme_Prop bernilai "onepiece", THEN THE Chatbot_Component SHALL menampilkan avatar fallback dan tetap merender tanpa menghentikan UI.

### Requirement 6: Chatbot Tema Default Tidak Berubah

**User Story:** Sebagai pengguna Dashboard biasa, saya ingin chatbot FinTracks tetap seperti semula, agar perubahan tema One Piece tidak mengganggu pengalaman di Dashboard.

#### Acceptance Criteria

1. WHERE Theme_Prop bernilai "fintracks", THE Chatbot_Component SHALL menampilkan judul persis "FinTracks AI".
2. WHERE Theme_Prop bernilai "fintracks", THE Chatbot_Component SHALL menampilkan header dengan warna sesuai Default_Theme (biru).
3. WHERE Theme_Prop bernilai "fintracks", THE Chatbot_Component SHALL menampilkan avatar emoji robot 🤖.

### Requirement 7: Ikon Tombol Toggle Chatbot pada Halaman One Piece

**User Story:** Sebagai pengguna di halaman One Piece, saya ingin tombol toggle chatbot menampilkan ikon Den Den Mushi, agar konsisten dengan tema One Piece, sementara di Dashboard biasa ikonnya tetap emoji robot.

#### Acceptance Criteria

1. WHILE pengguna berada di OnePiece_Page, THE Chatbot_Toggle_Button SHALL menampilkan DenDenMushi_Image sebagai ikon pada tombol mengambang di kanan bawah.
2. WHILE pengguna berada di Dashboard, THE Chatbot_Toggle_Button SHALL menampilkan emoji robot 🤖 sebagai ikon.
3. WHEN pengguna mengeklik Chatbot_Toggle_Button saat Chatbot_Component tersembunyi, THE FinTracks_App SHALL menampilkan Chatbot_Component.
4. WHEN pengguna mengeklik Chatbot_Toggle_Button saat Chatbot_Component tampil, THE FinTracks_App SHALL menyembunyikan Chatbot_Component.
5. IF DenDenMushi_Image gagal dimuat pada Chatbot_Toggle_Button di OnePiece_Page, THEN THE Chatbot_Toggle_Button SHALL menampilkan ikon fallback dan tetap berfungsi melakukan toggle.

### Requirement 8: Prasyarat File Gambar Den Den Mushi

**User Story:** Sebagai pengembang, saya ingin ketersediaan file gambar Den Den Mushi dicatat sebagai prasyarat, agar implementasi tidak gagal karena gambar belum tersedia.

#### Acceptance Criteria

1. THE Chatbot_Component SHALL merujuk DenDenMushi_Image dari lokasi `frontend/src/assets/den-den-mushi.png`.
2. WHEN DenDenMushi_Image tersedia pada lokasi tersebut, THE Chatbot_Component SHALL menampilkannya sebagai avatar pada OnePiece_Theme.
3. IF DenDenMushi_Image tidak tersedia pada lokasi tersebut, THEN THE FinTracks_App SHALL menampilkan teks alternatif atau ikon fallback pada elemen avatar OnePiece_Theme tanpa menghentikan UI.

## Assumptions and Dependencies

- File DenDenMushi_Image (`frontend/src/assets/den-den-mushi.png`) merupakan prasyarat yang harus disediakan pengguna sebelum implementasi dijalankan. Folder `frontend/src/assets/` sudah dibuat.
- Fitur ini murni re-skin visual pada sisi frontend. Backend tidak diubah.
- Logika khusus One Piece (misalnya pencarian produk atau figure) berada di luar scope fitur ini dan akan dipertimbangkan di kemudian hari.
- Stack frontend: React 18 + Vite + React Router v6 + Tailwind CSS.
