# Panduan Instalasi & Konfigurasi Gatling AI Copilot (MCP) di Windows

Panduan ini menjelaskan langkah demi langkah cara menyiapkan lingkungan kerja (setup) sistem **Gatling AI Copilot (MCP)** dari awal hingga akhir pada sistem operasi **Windows**.

Fokus utama ekosistem ini terdiri dari: Dashboard, AI Chatbot, MCP Server, Database (PostgreSQL), Mesin Gatling, dan RabbitMQ.

---

## 1. Persiapan Perangkat Lunak (Prerequisites)

Pastikan Anda telah mengunduh dan menginstal perangkat lunak berikut di Windows Anda:

1. **Python 3.10 atau lebih baru**
   - Saat instalasi, **WAJIB** centang kotak *"Add Python to PATH"*.
2. **Node.js (versi 18 LTS atau 20 LTS)**
   - Digunakan untuk menjalankan frontend React/Vite.
3. **Java Development Kit (JDK) 17 atau 21**
   - Wajib untuk menjalankan mesin Gatling (berbasis Scala).
   - Pastikan *Environment Variable* `JAVA_HOME` sudah diatur ke folder instalasi JDK.
4. **PostgreSQL (versi 14+)**
   - Digunakan sebagai database utama backend. 
   - Ingat *username* dan *password* postgres Anda (default biasanya user: `postgres`, password: `postgres`).
5. **Erlang & RabbitMQ Server**
   - Wajib untuk pengujian antrean (Queue) AMQP.
   - Unduh dan instal Erlang (OTP) terlebih dahulu, baru kemudian instal RabbitMQ Server untuk Windows.
6. **Ollama (Opsional, jika ingin AI Lokal)**
   - Unduh dari ollama.com dan jalankan `ollama run llama3.2`.

---

## 2. Instalasi Gatling

Gatling tidak diinstal seperti program biasa, melainkan diekstrak.

1. Unduh **Gatling Open Source** (versi bundle ZIP, misal 3.15.0) dari situs resminya.
2. Ekstrak file ZIP tersebut ke direktori yang mudah diakses, misalnya di `C:\gatling\`.
   - Pastikan folder bin berada di `C:\gatling\bin\`.
3. Gatling di Windows dijalankan menggunakan `gatling.bat`, **bukan** `gatling.sh`.

---

## 3. Clone / Salin Repository Project

Salin seluruh folder project dari Mac Anda ke laptop Windows (menggunakan Flashdisk, Git, atau Google Drive).

Buka **Terminal (Command Prompt / PowerShell)** di Windows, lalu navigasikan ke folder project:
```cmd
cd C:\path\to\Folder_Project_Anda
```

---

## 4. Konfigurasi Backend & MCP Server (Python)

Kita akan membuat *virtual environment* Python dan menginstal *dependencies*.

### A. Buat Virtual Environment
```cmd
python -m venv venv
venv\Scripts\activate
```
*(Pastikan muncul tulisan `(venv)` di sebelah kiri terminal Anda).*

### B. Instal Dependencies
```cmd
pip install -r backend/requirements.txt
pip install -r mcp-server/requirements.txt
```

### C. Konfigurasi File `.env` (Sangat Penting!)
Buka file `.env` yang ada di dalam folder `backend/` dan sesuaikan jalurnya untuk Windows. 
**Perbedaan utama di Windows adalah penulisan direktori dan file eksekusi Gatling:**

```ini
# --- DATABASE CONFIGURATION ---
# Sesuaikan password jika Anda mengubahnya saat instalasi PostgreSQL di Windows
DATABASE_URL=postgresql://postgres:password_anda@localhost:5432/fintracks

# --- OLLAMA LOCAL AI CONFIGURATION ---
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_TIMEOUT=300

# --- GATLING PATHS (UBAH KE FORMAT WINDOWS) ---
# Gunakan double backslash (\\) atau single forward slash (/)
GATLING_HOME=C:/gatling
GATLING_BIN_PATH=C:/gatling/bin/gatling.bat
GATLING_SIMULATIONS_DIR=C:/gatling/user-files/simulations
GATLING_RESULTS_DIR=C:/gatling/results

# --- RABBITMQ CONFIGURATION ---
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
```
*(Catatan: Lakukan hal yang sama pada file `.env` di direktori utama/root jika ada).*

### D. Inisialisasi Database (Migrasi)
Masih di terminal dengan `(venv)` aktif:
```cmd
cd backend
python -m alembic upgrade head
cd ..
```

### E. Jalankan Backend
Kembali ke folder utama project, lalu jalankan:
```cmd
python backend/run.py
```
*Biarkan terminal ini terbuka. Backend sekarang berjalan di `http://127.0.0.1:8000`.*

---

## 5. Menjalankan MCP Server

Buka **Terminal Baru** (juga di folder project utama), aktifkan kembali virtual environment, lalu jalankan MCP Server:

```cmd
venv\Scripts\activate
python mcp-server/server.py
```
*Biarkan terminal ini terbuka. MCP Server sekarang berjalan dan mendengarkan instruksi Gatling.*

---

## 6. Konfigurasi & Menjalankan Frontend (React)

Buka **Terminal Baru (Ketiga)**, arahkan ke folder frontend:

```cmd
cd frontend
```

### A. Instal Dependencies Node.js
```cmd
npm install
```

### B. Jalankan Frontend
```cmd
npm run dev
```
*Frontend Anda sekarang dapat diakses melalui browser di alamat `http://localhost:3000` atau `http://localhost:5173`.*

---

## 7. Pengujian (Testing)

1. Buka browser dan akses **Dashboard Frontend**.
2. Buka menu **Gatling AI Copilot**.
3. Pastikan indikator koneksi di pojok kanan atas menunjukkan "Online".
4. Pada *dropdown* AI Engine, pilih **Local LLM**.
5. Coba ketik prompt: `"Buatkan skrip test untuk https://example.com dengan 10 VU"`
6. Jika AI membalas dan berhasil membuat skrip, artinya keseluruhan konfigurasi Windows Anda **SUKSES 100%**!

---
**Tips Troubleshooting Windows:**
- Jika `gatling.bat` gagal dijalankan, pastikan `JAVA_HOME` sudah diatur di System Properties > Environment Variables.
- Jika script Python menolak untuk berjalan karena *execution policy* di PowerShell, jalankan PowerShell sebagai Administrator lalu ketik: `Set-ExecutionPolicy RemoteSigned`
