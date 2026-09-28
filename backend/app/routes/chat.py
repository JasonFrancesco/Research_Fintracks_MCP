import os
import re
import json
import requests
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from ..auth.dependencies import get_current_user
from ..models.models import User

router = APIRouter(prefix="/chat", tags=["AI Chatbot"])

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001/call")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30"))

def get_active_model() -> str:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    raw = os.getenv("ACTIVE_MODEL", "ollama/llama3.2").strip()
    if not raw:
        raw = "ollama/llama3.2"
    return raw.split("/", 1)[1] if "/" in raw else raw

# Skema resmi MCP Tools yang di-expose ke LLM (Sesuai Spesifikasi MCP Function Calling)
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "create_transaction",
            "description": "Catat transaksi keuangan baru (pemasukan/gaji atau pengeluaran/pembelian) ke dalam database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Judul atau deskripsi transaksi (contoh: Makan Siang Nasi Goreng, Beli Kopi Starbucks, Gaji Bulanan)."
                    },
                    "amount": {
                        "type": "number",
                        "description": "Nominal transaksi dalam angka Rupiah tanpa simbol (contoh: 25000 untuk 25 ribu/25k, 1500000 untuk 1.5 juta)."
                    },
                    "category": {
                        "type": "string",
                        "description": "Kategori transaksi. Pilih dari: 'Makanan & Minuman', 'Transportasi', 'Belanja', 'Pendapatan', 'Kesehatan', 'Hiburan', 'Tagihan', atau 'Lainnya'."
                    },
                    "transaction_type": {
                        "type": "string",
                        "enum": ["income", "expense"],
                        "description": "Jenis transaksi: 'expense' untuk pengeluaran/beli/bayar, 'income' untuk pemasukan/gaji/terima uang."
                    },
                    "date": {
                        "type": "string",
                        "description": "Tanggal transaksi format YYYY-MM-DD. Gunakan tanggal hari ini jika pengguna tidak menyebutkan tanggal spesifik."
                    },
                    "note": {
                        "type": "string",
                        "description": "Catatan tambahan opsional."
                    }
                },
                "required": ["title", "amount", "category", "transaction_type", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions",
            "description": "Mengambil riwayat atau daftar transaksi keuangan terbaru milik pengguna.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Jumlah transaksi terbaru yang ingin diambil (default 10)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_summary",
            "description": "Mendapatkan ringkasan statistik keuangan (Total Pemasukan, Total Pengeluaran, dan Saldo akhir).",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_transaction",
            "description": "Mengubah data transaksi yang sudah ada berdasarkan ID transaksi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "integer",
                        "description": "ID transaksi numerik yang ingin diubah."
                    },
                    "title": {"type": "string", "description": "Judul baru (opsional)"},
                    "amount": {"type": "number", "description": "Nominal baru (opsional)"},
                    "category": {"type": "string", "description": "Kategori baru (opsional)"},
                    "transaction_type": {"type": "string", "enum": ["income", "expense"], "description": "Jenis transaksi baru (opsional)"},
                    "date": {"type": "string", "description": "Tanggal baru format YYYY-MM-DD (opsional)"},
                    "note": {"type": "string", "description": "Catatan baru (opsional)"}
                },
                "required": ["transaction_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_transaction",
            "description": "Menghapus catatan transaksi keuangan berdasarkan ID transaksi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "integer",
                        "description": "ID transaksi numerik yang ingin dihapus."
                    }
                },
                "required": ["transaction_id"]
            }
        }
    }
]

def call_mcp_tool(tool_name: str, arguments: dict) -> Optional[str]:
    """Memanggil tool pada MCP Server (port 8001)"""
    try:
        api_key = os.getenv("MCP_API_KEY", "default-dev-key-123")
        payload = {
            "name": tool_name,
            "arguments": arguments,
            "api_key": api_key
        }
        res = requests.post(MCP_SERVER_URL, json=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                return str(data.get("result"))
            else:
                return f"Error dari MCP Server: {data.get('error')}"
    except Exception as e:
        print(f"Error calling MCP Tool {tool_name}: {e}")
        return f"Gagal terhubung ke MCP Server: {e}"
    return None

def sanitize_tool_args(tool_name: str, args: dict, user_id: int, user_msg: str) -> dict:
    """Sanitasi dan melengkapi argumen tool sebelum dikirim ke MCP Server"""
    args["user_id"] = user_id
    today_str = datetime.now().strftime("%Y-%m-%d")

    if tool_name == "create_transaction":
        if "title" not in args or not args["title"]:
            # Bersihkan kata perintah untuk mengambil judul transaksi
            clean_t = re.sub(r'\b(catat|tambah|pemasukan|pengeluaran|bayar|beli|sebesar|rp|ribu|k|hari ini|kemarin)\b', '', user_msg, flags=re.IGNORECASE)
            clean_t = re.sub(r'\d+(?:[\.,]\d+)?', '', clean_t).strip()
            args["title"] = clean_t.capitalize() if clean_t else "Transaksi Baru"

        if "amount" in args and args["amount"] is not None:
            try:
                args["amount"] = float(args["amount"])
            except (ValueError, TypeError):
                args["amount"] = 0.0
        else:
            args["amount"] = 0.0

        if "date" not in args or not args["date"]:
            args["date"] = today_str

        if "transaction_type" not in args or args["transaction_type"] not in ["income", "expense"]:
            msg_lower = user_msg.lower()
            args["transaction_type"] = "income" if any(k in msg_lower for k in ["gaji", "terima", "masuk", "bonus", "pemasukan"]) else "expense"

        valid_cats = ["Makanan & Minuman", "Transportasi", "Belanja", "Pendapatan", "Kesehatan", "Hiburan", "Tagihan", "Lainnya"]
        if "category" not in args or not args["category"] or args["category"] not in valid_cats:
            msg_lower = user_msg.lower()
            if any(k in msg_lower for k in ["makan", "minum", "resto", "cafe", "nasi", "kopi", "warung"]):
                args["category"] = "Makanan & Minuman"
            elif any(k in msg_lower for k in ["bensin", "transport", "gojek", "grab", "parkir", "tol"]):
                args["category"] = "Transportasi"
            elif any(k in msg_lower for k in ["belanja", "baju", "sepatu", "tokopedia", "shopee"]):
                args["category"] = "Belanja"
            elif any(k in msg_lower for k in ["gaji", "bonus", "transfer masuk"]):
                args["category"] = "Pendapatan"
            else:
                args["category"] = "Lainnya"

    elif tool_name == "get_transactions":
        if "limit" not in args or not args["limit"]:
            args["limit"] = 10
        else:
            try:
                args["limit"] = int(args["limit"])
            except (ValueError, TypeError):
                args["limit"] = 10

    elif tool_name in ["update_transaction", "delete_transaction"]:
        if "transaction_id" in args and args["transaction_id"] is not None:
            try:
                args["transaction_id"] = int(args["transaction_id"])
            except (ValueError, TypeError):
                pass

    return args

@router.post("/", response_model=ChatResponse)
async def chat_with_ai(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    user_msg = request.message.strip()
    user_id = current_user.id
    active_model = get_active_model()
    today_str = datetime.now().strftime("%Y-%m-%d")

    system_prompt = (
        f"Anda adalah FinTracks AI Assistant, asisten keuangan pribadi yang cerdas.\n"
        f"User ID: {user_id}. Tanggal hari ini: {today_str}.\n"
        f"Anda memiliki akses ke MCP Tools untuk mengelola data keuangan pengguna:\n"
        f"- create_transaction: Mencatat transaksi baru (pemasukan/pengeluaran).\n"
        f"- get_transactions: Melihat riwayat transaksi.\n"
        f"- get_summary: Melihat ringkasan pemasukan, pengeluaran, dan saldo.\n"
        f"- update_transaction: Mengubah transaksi yang sudah ada.\n"
        f"- delete_transaction: Menghapus transaksi.\n\n"
        f"Aturan Utama:\n"
        f"1. Jika pengguna meminta aksi keuangan (catat, lihat, ubah, hapus, cek saldo/summary), "
        f"Anda WAJIB memanggil MCP Tool yang sesuai.\n"
        f"2. Jawablah dengan bahasa Indonesia yang ramah, sopan, dan jelas."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg}
    ]

    try:
        # Step 1: Kirim request ke Ollama bersama definisi MCP Tools
        payload = {
            "model": active_model,
            "messages": messages,
            "tools": TOOLS_SCHEMA,
            "stream": False,
            "options": {"temperature": 0.2}
        }
        res = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        
        # Jika model tidak mendukung native function calling (HTTP 400 "does not support tools")
        if res.status_code == 400 and "does not support tools" in res.text:
            print(f"[Ollama Warning] Model '{active_model}' tidak mendukung native function calling. Memanggil dalam mode standar.")
            fallback_payload = {
                "model": active_model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.5}
            }
            res = requests.post(OLLAMA_URL, json=fallback_payload, timeout=OLLAMA_TIMEOUT)

        if res.status_code != 200:
            print(f"[Ollama Error] HTTP {res.status_code}: {res.text}")
            return ChatResponse(response=f"🤖 **FinTracks AI:** Model '{active_model}' mengembalikan error (HTTP {res.status_code}). Coba gunakan 'ollama/llama3.2'.")

        res_data = res.json()
        ai_message = res_data.get("message", {})
        tool_calls = ai_message.get("tool_calls", [])

        # Step 2: Jika AI memutuskan untuk memanggil MCP Tool
        if tool_calls:
            print(f"[Agentic MCP] Model '{active_model}' memutuskan memanggil {len(tool_calls)} tool(s).")
            tool_outputs = []

            for tool_call in tool_calls:
                fn_name = tool_call.get("function", {}).get("name")
                fn_args = tool_call.get("function", {}).get("arguments", {})

                print(f"[Agentic MCP Executing] Tool: {fn_name} | Raw Args: {fn_args}")

                # Sanitasi dan inject user_id ke argumen tool
                sanitized_args = sanitize_tool_args(fn_name, fn_args, user_id, user_msg)

                # Panggil MCP Server
                mcp_result = call_mcp_tool(fn_name, sanitized_args)
                print(f"[MCP Result] {mcp_result}")

                tool_outputs.append(str(mcp_result or "Operasi MCP selesai."))

            # Step 3: Sintesis respon akhir yang ramah & manusiawi berdasarkan hasil MCP Tool
            synthesis_messages = [
                {
                    "role": "system", 
                    "content": "Anda adalah FinTracks AI Assistant. Tugas Anda adalah menyampaikan hasil eksekusi MCP Tool kepada pengguna secara ramah, sopan, rapi, dan jelas dalam Bahasa Indonesia."
                },
                {
                    "role": "user", 
                    "content": f"Pesan Pengguna: '{user_msg}'\nHasil Eksekusi MCP Tool: {tool_outputs[0]}"
                }
            ]

            synth_res = requests.post(
                OLLAMA_URL, 
                json={"model": active_model, "messages": synthesis_messages, "stream": False, "options": {"temperature": 0.5}}, 
                timeout=OLLAMA_TIMEOUT
            )
            
            if synth_res.status_code == 200:
                final_ai_msg = synth_res.json().get("message", {}).get("content", "")
                if final_ai_msg:
                    return ChatResponse(response=final_ai_msg)

            # Fallback jika final LLM response kosong
            return ChatResponse(response=f"🤖 **FinTracks AI Assistant:**\n\n" + "\n\n".join(tool_outputs))

        # Step 4: Jika AI tidak memerlukan tool (percakapan umum/tanya jawab)
        direct_response = ai_message.get("content", "")
        if direct_response:
            return ChatResponse(response=direct_response)

        return ChatResponse(response="🤖 **FinTracks AI Assistant:** Maaf, saya tidak dapat memahami permintaan Anda.")

    except requests.exceptions.Timeout:
        return ChatResponse(response=f"🤖 **FinTracks AI:** Respon model AI ({active_model}) mengalami timeout. Coba gunakan model yang lebih ringan.")
    except Exception as e:
        print(f"[Agentic Error] {e}")
        return ChatResponse(response=f"🤖 **FinTracks AI:** Terjadi kesalahan saat memproses pesan: {str(e)}")

