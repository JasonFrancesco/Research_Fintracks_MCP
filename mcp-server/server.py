import os
import sys
import asyncio
import argparse
from pathlib import Path
from typing import Optional

import anyio
from mcp.server.fastmcp import FastMCP

# Ensure mcp-server root directory is in sys.path
server_dir = str(Path(__file__).resolve().parent)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from tools.transaction_tools import (
    create_transaction_tool,
    get_transactions_tool,
    update_transaction_tool,
    delete_transaction_tool,
    get_summary_tool
)

# Port & path endpoint MCP HTTP streamable. Backend terhubung ke
# http://127.0.0.1:8001/mcp sebagai MCP client (protokol MCP, bukan REST).
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")

# Inisialisasi FastMCP Server dengan transport HTTP streamable.
# stateless_http=True: tiap request MCP berdiri sendiri tanpa sesi persisten,
# cocok untuk backend yang connect-list-call-close per permintaan chat.
mcp = FastMCP(
    name="FinTracks MCP Server",
    instructions="MCP Server untuk pencatatan dan pengelolaan keuangan pribadi FinTracks",
    host=MCP_HOST,
    port=MCP_PORT,
    streamable_http_path=MCP_PATH,
    stateless_http=True,
)

# Registrasi Tools menggunakan Decorator @mcp.tool()
@mcp.tool()
def create_transaction(
    user_id: int,
    title: str,
    amount: float,
    category: str,
    transaction_type: str,
    date: str,
    note: Optional[str] = None
) -> str:
    """
    Catat transaksi keuangan baru (pemasukan/gaji atau pengeluaran/pembelian).

    - amount: nominal Rupiah tanpa simbol (25000 untuk 25rb, 1500000 untuk 1.5 juta).
    - category: pilih salah satu dari 'Makanan & Minuman', 'Transportasi', 'Belanja',
      'Pendapatan', 'Kesehatan', 'Hiburan', 'Tagihan', 'Lainnya'.
    - transaction_type: 'expense' untuk pengeluaran/beli/bayar, 'income' untuk
      pemasukan/gaji/terima uang.
    - date: format YYYY-MM-DD. Pakai tanggal hari ini jika pengguna tidak menyebut tanggal.
    """
    return create_transaction_tool(user_id, title, amount, category, transaction_type, date, note)

@mcp.tool()
def get_transactions(
    user_id: int,
    limit: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    transaction_type: Optional[str] = None,
) -> str:
    """
    Mengambil riwayat/daftar transaksi keuangan milik pengguna, terbaru lebih dulu.

    Semua filter opsional. WAJIB dipakai bila pengguna menyebut tanggal atau jenis
    transaksi, jangan memilah sendiri dari daftar tanpa filter.
    - limit: jumlah transaksi yang ditampilkan, default 10.
    - start_date: tanggal YYYY-MM-DD. Untuk SATU tanggal (contoh "pengeluaran tanggal 29
      September"), isi start_date saja.
    - end_date: tanggal akhir YYYY-MM-DD, dipakai untuk rentang (contoh "minggu ini",
      "bulan September": start_date=2026-09-01, end_date=2026-09-30).
    - transaction_type: 'expense' untuk pengeluaran, 'income' untuk pemasukan.

    Jika filter dipakai, hasil memuat jumlah dan total nominal yang sudah dihitung.
    Jika tidak ada data, hasil menyatakannya secara eksplisit; sampaikan apa adanya.
    """
    return get_transactions_tool(user_id, limit, start_date, end_date, transaction_type)

@mcp.tool()
def update_transaction(
    user_id: int,
    transaction_id: Optional[int] = None,
    match_title: Optional[str] = None,
    match_date: Optional[str] = None,
    title: Optional[str] = None,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    transaction_type: Optional[str] = None,
    date: Optional[str] = None,
    note: Optional[str] = None
) -> str:
    """
    Ubah data transaksi keuangan yang sudah ada.

    Target transaksi ditentukan lewat salah satu cara berikut, wajib ada minimal satu:
    - transaction_id: ID numerik transaksi, cara paling pasti.
    - match_title: kata kunci judul transaksi yang dicari, dipakai bila ID tidak diketahui.
    - match_date: tanggal transaksi yang dicari, format YYYY-MM-DD.
    match_title dan match_date boleh dikombinasikan untuk mempersempit pencarian.
    Jika kriteria pencarian cocok dengan lebih dari satu transaksi, tidak ada data
    yang diubah dan tool mengembalikan daftar kandidat beserta ID-nya.

    Parameter title, amount, category, transaction_type, date, dan note adalah
    NILAI BARU. Jangan tertukar: 'title' mengubah judul, 'match_title' mencari judul.
    """
    updates = {}
    if title is not None: updates["title"] = title
    if amount is not None: updates["amount"] = amount
    if category is not None: updates["category"] = category
    if transaction_type is not None: updates["transaction_type"] = transaction_type
    if date is not None: updates["date"] = date
    if note is not None: updates["note"] = note
    return update_transaction_tool(
        user_id=user_id,
        transaction_id=transaction_id,
        match_title=match_title,
        match_date=match_date,
        **updates,
    )

@mcp.tool()
def delete_transaction(transaction_id: int, user_id: int) -> str:
    """Hapus catatan transaksi keuangan berdasarkan ID transaksi."""
    return delete_transaction_tool(transaction_id, user_id)

@mcp.tool()
def get_summary(user_id: int) -> str:
    """Mendapatkan ringkasan keuangan (Total Pemasukan, Total Pengeluaran, dan Saldo)."""
    return get_summary_tool(user_id)


# Aplikasi ASGI MCP HTTP streamable. Di-expose di level modul agar bisa
# dijalankan dengan: uvicorn server:app_http --host 127.0.0.1 --port 8001
app_http = mcp.streamable_http_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinTracks FastMCP Server")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Jalankan sebagai MCP server stdio (untuk Claude Desktop / Cursor)",
    )
    args = parser.parse_args()

    if args.stdio:
        # Mode stdio MCP standar: server bicara protokol MCP lewat stdin/stdout.
        mcp.run(transport="stdio")
    else:
        # Mode HTTP streamable: protokol MCP di atas HTTP, dipakai backend web app.
        print("==================================================")
        print(f"[FinTracks] {mcp.name} (FastMCP, HTTP streamable)")
        print(f"   Endpoint MCP : http://{MCP_HOST}:{MCP_PORT}{MCP_PATH}")
        print(f"   Mode stdio   : python server.py --stdio")
        print("==================================================")
        # Setara dengan mcp.run(transport="streamable-http"), tetapi di Windows
        # memakai SelectorEventLoop. Event loop default Windows (ProactorEventLoop)
        # mencetak "ERROR Exception in callback _ProactorBasePipeTransport.
        # _call_connection_lost ... connection was forcibly closed by the remote host"
        # setiap kali client memutus koneksi lebih dulu. Request-nya sendiri sudah
        # selesai (200 OK), tetapi traceback itu membanjiri log. Selector loop tidak
        # punya jalur kode tersebut. Kekurangannya, selector loop di Windows tidak
        # mendukung subprocess, dan mode HTTP ini memang tidak memakainya.
        backend_options = (
            {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
        )
        anyio.run(mcp.run_streamable_http_async, backend_options=backend_options)


