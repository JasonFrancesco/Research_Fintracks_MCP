"""
MCP client untuk backend FinTracks.

Backend adalah MCP host+client: ia memegang LLM dan berbicara ke mcp-server
memakai protokol MCP yang sebenarnya (initialize -> tools/list -> tools/call)
di atas transport HTTP streamable. Ini menggantikan pemanggilan REST
`POST /call` buatan sendiri pada versi lama.

Pola koneksi: connect -> initialize -> operasi -> close, dilakukan per operasi.
Server berjalan dengan stateless_http=True sehingga tiap request berdiri sendiri,
dan pola ini membuat backend tahan terhadap server MCP yang sempat restart tanpa
perlu mengelola sesi persisten atau logika reconnect yang rumit.
"""
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _mcp_url() -> str:
    """
    URL endpoint MCP server. Dibaca dari env setiap dipanggil agar konsisten
    dengan pola konfigurasi runtime lain di backend (lihat get_ollama_runtime).
    """
    host = (os.getenv("MCP_HOST") or "127.0.0.1").strip()
    port = (os.getenv("MCP_PORT") or "8001").strip()
    path = (os.getenv("MCP_PATH") or "/mcp").strip()
    if not path.startswith("/"):
        path = "/" + path
    return f"http://{host}:{port}{path}"


@asynccontextmanager
async def _session():
    """Membuka session MCP yang sudah ter-initialize, lalu menutupnya rapi."""
    url = _mcp_url()
    # streamablehttp_client membuka koneksi HTTP ke server MCP dan memberi kita
    # dua "pipa": read_stream (baca balasan server) & write_stream (kirim ke server).
    async with streamablehttp_client(url) as (read_stream, write_stream, _):
        # ClientSession membungkus kedua pipa itu jadi API MCP yang rapi
        # (punya .initialize(), .list_tools(), .call_tool(), dst).
        async with ClientSession(read_stream, write_stream) as session:
            # initialize() = handshake wajib MCP. Harus dipanggil sebelum
            # tools/list atau tools/call, kalau tidak server menolak.
            await session.initialize()
            yield session  # serahkan session ke pemanggil; koneksi ditutup otomatis setelah blok selesai


async def list_tools() -> List[Dict[str, Any]]:
    """
    Mengambil daftar tool DARI server via tools/list.

    Inilah pengganti TOOLS_SCHEMA manual: definisi tool datang dari server
    sebagai satu-satunya sumber kebenaran. Hasilnya berupa list dict dengan
    kunci name / description / inputSchema, siap diterjemahkan oleh
    schema_adapter ke format function-calling LLM.
    """
    async with _session() as session:
        # Kirim permintaan tools/list ke server, dapatkan daftar tool + schema-nya.
        result = await session.list_tools()
        # Ubah objek Tool dari SDK menjadi dict sederhana supaya mudah dipakai
        # bagian lain (schema_adapter). inputSchema = bentuk argumen tiap tool.
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema or {"type": "object", "properties": {}},
            }
            for tool in result.tools
        ]


async def call_tool(name: str, arguments: Dict[str, Any]) -> str:
    """
    Menjalankan satu tool via tools/call, lalu mengembalikan hasilnya sebagai teks.

    MCP mengembalikan konten terstruktur (daftar blok). Untuk FinTracks seluruh
    tool mengembalikan satu blok teks, jadi blok-blok teks digabung dengan newline.
    Jika server menandai hasil sebagai error (isError), pesannya tetap dikembalikan
    sebagai teks agar bisa disintesis dan ditampilkan ke pengguna, bukan dilempar
    sebagai exception yang mematikan alur chat.
    """
    async with _session() as session:
        # Minta server menjalankan satu tool (mis. get_transactions) dengan argumennya.
        result = await session.call_tool(name, arguments)

        # Balasan MCP berupa daftar "blok" konten. Ambil hanya blok bertipe teks,
        # lalu gabungkan jadi satu string.
        texts = [
            block.text
            for block in (result.content or [])
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ]
        output = "\n".join(texts).strip()

        # result.isError = True kalau tool gagal di server. Pesannya tetap
        # dikembalikan sebagai teks biasa (bukan dilempar exception) supaya alur
        # chat tidak mati dan errornya bisa ditampilkan ke pengguna.
        if result.isError:
            return output or f"Tool '{name}' mengembalikan error tanpa detail."
        return output or f"Tool '{name}' selesai tanpa keluaran."
