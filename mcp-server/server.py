import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

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

app = FastAPI(title="FinTracks MCP AI Server")

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

TOOLS_REGISTRY = {
    "create_transaction": create_transaction_tool,
    "get_transactions": get_transactions_tool,
    "update_transaction": update_transaction_tool,
    "delete_transaction": delete_transaction_tool,
    "get_summary": get_summary_tool
}

def verify_api_key(api_key: Optional[str]):
    if not api_key or api_key != MCP_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")

@app.get("/")
def root():
    return {
        "status": "online",
        "server": "FinTracks MCP AI Server",
        "port": 8001,
        "tools": list(TOOLS_REGISTRY.keys())
    }

@app.get("/tools")
def list_tools():
    return {"tools": list(TOOLS_REGISTRY.keys())}

@app.post("/call")
def call_tool(req: ToolCallRequest):
    verify_api_key(req.api_key)
    tool_func = TOOLS_REGISTRY.get(req.name)
    if not tool_func:
        raise HTTPException(status_code=404, detail=f"Tool '{req.name}' not found")
    try:
        result = tool_func(**req.arguments)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    print("==================================================")
    print("FinTracks MCP AI Server berjalan di port 8001!")
    print("   URL: http://127.0.0.1:8001")
    print("==================================================")
    uvicorn.run(app, host="127.0.0.1", port=8001)
