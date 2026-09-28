import os
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

# Ensure mcp-server root directory is in sys.path
server_dir = str(Path(__file__).resolve().parent)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from config import get_db_session, MCP_API_KEY
from tools.transaction_tools import (
    create_transaction_tool,
    get_transactions_tool,
    update_transaction_tool,
    delete_transaction_tool,
    get_summary_tool
)

# Inisialisasi FastMCP Server (Sesuai pola FastMCP pada tutorial YouTube)
mcp = FastMCP(
    name="FinTracks MCP Server",
    instructions="MCP Server untuk pencatatan dan pengelolaan keuangan pribadi FinTracks"
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
    """Catat transaksi keuangan baru (income atau expense). Format tanggal 'YYYY-MM-DD'."""
    return create_transaction_tool(user_id, title, amount, category, transaction_type, date, note)

@mcp.tool()
def get_transactions(user_id: int, limit: int = 10) -> str:
    """Mengambil daftar riwayat transaksi keuangan terbaru untuk user tertentu."""
    return get_transactions_tool(user_id, limit)

@mcp.tool()
def update_transaction(
    transaction_id: int,
    user_id: int,
    title: Optional[str] = None,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    transaction_type: Optional[str] = None,
    date: Optional[str] = None,
    note: Optional[str] = None
) -> str:
    """Ubah data transaksi keuangan yang sudah ada berdasarkan ID."""
    updates = {}
    if title is not None: updates["title"] = title
    if amount is not None: updates["amount"] = amount
    if category is not None: updates["category"] = category
    if transaction_type is not None: updates["transaction_type"] = transaction_type
    if date is not None: updates["date"] = date
    if note is not None: updates["note"] = note
    return update_transaction_tool(transaction_id, user_id, **updates)

@mcp.tool()
def delete_transaction(transaction_id: int, user_id: int) -> str:
    """Hapus catatan transaksi keuangan berdasarkan ID."""
    return delete_transaction_tool(transaction_id, user_id)

@mcp.tool()
def get_summary(user_id: int) -> str:
    """Mendapatkan ringkasan keuangan (Total Pemasukan, Total Pengeluaran, dan Saldo)."""
    return get_summary_tool(user_id)


# FastAPI Wrapper untuk melayani HTTP Request dari Web App FinTracks
app = FastAPI(title="FinTracks MCP Server API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}
    api_key: Optional[str] = None

def verify_api_key(api_key: Optional[str]):
    if not api_key or api_key != MCP_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")

@app.get("/")
def root():
    return {
        "status": "online",
        "server": mcp.name,
        "framework": "FastMCP",
        "port": 8001,
        "tools": [t.name for t in mcp._tool_manager.list_tools()]
    }

@app.get("/tools")
def list_tools():
    return {"tools": [t.name for t in mcp._tool_manager.list_tools()]}

@app.post("/call")
async def call_tool(req: ToolCallRequest):
    verify_api_key(req.api_key)
    try:
        res, extra = await mcp.call_tool(req.name, req.arguments)
        text_output = "\n".join([c.text for c in res if hasattr(c, "text")])
        return {"success": True, "result": text_output}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinTracks FastMCP Server")
    parser.add_argument("--stdio", action="store_true", help="Menjalankan server dalam mode stdio MCP standar")
    args = parser.parse_args()

    if args.stdio:
        # Mode Stdio MCP Standar (untuk Claude Desktop / Cursor / Antigravity MCP Client)
        mcp.run(transport="stdio")
    else:
        # Mode HTTP Server (untuk koneksi Backend FastAPI & Web App)
        import uvicorn
        print("==================================================")
        print(f"[FinTracks] {mcp.name} (FastMCP) berjalan di port 8001!")
        print("   HTTP API: http://127.0.0.1:8001")
        print("   Stdio Mode: python server.py --stdio")
        print("==================================================")
        uvicorn.run(app, host="127.0.0.1", port=8001)


