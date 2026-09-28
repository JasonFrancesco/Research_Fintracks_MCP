import os
import re
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from ..auth.dependencies import get_current_user
from ..models.models import User

router = APIRouter(prefix="/chat", tags=["AI Chatbot"])

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

MCP_SERVER_URL = "http://127.0.0.1:8001/call"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.2"

def call_mcp_tool(tool_name: str, arguments: dict) -> Optional[str]:
    """Memanggil tool pada MCP Server (port 8001)"""
    try:
        api_key = os.getenv("MCP_API_KEY", "default-dev-key-123")
        payload = {
            "name": tool_name,
            "arguments": arguments,
            "api_key": api_key
        }
        res = requests.post(MCP_SERVER_URL, json=payload, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                return str(data.get("result"))
    except Exception as e:
        print(f"Error calling MCP Tool {tool_name}: {e}")
    return None

def parse_amount(text: str) -> float:
    """Ekstrak nominal dari teks, handle 'k' sebagai ribuan dan hapus titik/koma ribuan"""
    text = text.lower().replace('.', '').replace(',', '')
    match = re.search(r'(\d+)\s*k', text)
    if match:
        return float(match.group(1)) * 1000
    amounts = re.findall(r'\d+', text)
    return float(amounts[0]) if amounts else 0.0

def parse_date_for_delete(text: str) -> Optional[str]:
    """Ekstrak tanggal sederhana dari teks untuk keperluan delete/update"""
    from datetime import datetime, timedelta
    text = text.lower()
    today = datetime.now()
    if "hari ini" in text:
        return today.strftime("%Y-%m-%d")
    if "kemarin" in text:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    match = re.search(r'\d{4}-\d{2}-\d{2}', text)
    if match:
        return match.group(0)
    return None

def extract_delete_params(message: str):
    """Ekstrak judul dan tanggal dari pesan penghapusan"""
    msg_lower = message.lower()
    clean_text = re.sub(r'(hapus|delete|hilangkan|buang|remove|transaksi|catatan)', '', msg_lower, flags=re.IGNORECASE).strip()
    date_val = parse_date_for_delete(msg_lower)
    if date_val:
        clean_text = clean_text.replace("hari ini", "").replace("kemarin", "").strip()
        clean_text = re.sub(r'\d{4}-\d{2}-\d{2}', '', clean_text).strip()
    return clean_text, date_val

def find_matching_transaction(res_tx: str, target_title: str, target_date: Optional[str] = None, target_id: Optional[str] = None):
    """Mencari ID transaksi yang cocok dari output string format MCP get_transactions"""
    lines = res_tx.split('\n')
    for line in lines:
        line = line.strip()
        if not line or '[' not in line or ']' not in line:
            continue
        try:
            id_match = re.search(r'\[(\d+)\]', line)
            if not id_match:
                continue
            tx_id = id_match.group(1)
            content = line.split(']', 1)[1].strip()
            parts = [p.strip() for p in content.split('|')]
            tx_date = parts[0] if len(parts) > 0 else ""
            tx_title = parts[1].lower() if len(parts) > 1 else ""

            # 1. If target_id is provided, match ONLY by ID
            if target_id:
                if tx_id == str(target_id):
                    return tx_id, parts[1] if len(parts) > 1 else ""
                continue

            # 2. Match by Title and Date
            title_match = (not target_title) or (target_title.lower() in tx_title) or (tx_title in target_title.lower())
            date_match = (not target_date) or (target_date in tx_date)

            if title_match and date_match:
                return tx_id, parts[1] if len(parts) > 1 else ""
        except Exception:
            continue
    return None, None

def extract_transaction_details(message: str):
    """Ekstrak judul, nominal, dan kategori dari pesan user dengan logika hybrid (Keyword + AI)"""
    msg_lower = message.lower()
    tx_type = "income" if any(k in msg_lower for k in ["pemasukan", "gaji", "terima", "masuk", "transfer masuk", "bonus"]) else "expense"
    amount = parse_amount(message)
    category = "Lainnya"
    cat_map = {
        "Makanan & Minuman": ["makan", "minum", "resto", "cafe", "warung", "ayam", "nasi", "kopi", "bakso", "mie", "snack", "cemilan", "starbucks", "mcdo", "kfc", "go-food", "grab-food"],
        "Transportasi": ["bensin", "transport", "gojek", "grab", "ojek", "taxi", "tiket", "parkir", "tol", "kereta", "bus", "pesawat", "go-ride", "go-car"],
        "Belanja": ["belanja", "shopee", "tokopedia", "mall", "pasar", "beli", "skin-care", "baju", "sepatu", "elektronik", "lazada"],
        "Pendapatan": ["gaji", "bonus", "komisi", "hadiah", "transfer masuk", "investasi"],
        "Kesehatan": ["obat", "dokter", "rumah sakit", "klinik", "apotek", "vitamin", "checkup"],
        "Hiburan": ["bioskop", "netflix", "spotify", "game", "konser", "wisata", "jalan-jalan"],
        "Tagihan": ["listrik", "air", "wifi", "internet", "bpjs", "kos", "kontrakan", "cicilan"]
    }
    for cat, keywords in cat_map.items():
        if any(k in msg_lower for k in keywords):
            category = cat
            break
    clean_title = re.sub(r'(catat|tambah|beli|pemasukan|pengeluaran|makanan|minuman|dengan harga|harga|nominal|rupiah|rp|hari ini|tadi|besok|kemarin)', '', msg_lower, flags=re.IGNORECASE)
    clean_title = re.sub(r'\d+\s*k?', '', clean_title)
    clean_title = clean_title.strip(',. ').strip()
    if not clean_title:
        clean_title = "Transaksi Baru"
    return tx_type, amount, category, clean_title.capitalize()

@router.post("/", response_model=ChatResponse)
async def chat_with_ai(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    user_msg = request.message.strip()
    msg_lower = user_msg.lower()
    user_id = current_user.id

    # 1. DELETE: Hapus Transaksi (Diutamakan sebelum READ)
    if any(k in msg_lower for k in ["hapus", "delete", "hilangkan", "buang", "remove"]):
        target_title, target_date = extract_delete_params(user_msg)
        id_match_prompt = re.search(r'\b(?:id|#)\s*(\d+)\b', msg_lower)
        target_id = id_match_prompt.group(1) if id_match_prompt else (target_title if target_title.isdigit() else None)

        res_tx = call_mcp_tool("get_transactions", {"user_id": user_id, "limit": 50})
        if res_tx:
            matching_tx_id, tx_title_found = find_matching_transaction(
                res_tx,
                target_title="" if target_id else target_title,
                target_date=target_date,
                target_id=target_id
            )
            if matching_tx_id:
                del_res = call_mcp_tool("delete_transaction", {"transaction_id": int(matching_tx_id), "user_id": user_id})
                return ChatResponse(response=f"🤖 **FinTracks AI Assistant:**\n\n{del_res if del_res else f'Transaksi `{tx_title_found or matching_tx_id}` berhasil dihapus.'}")
            else:
                detail_str = f"ID [{target_id}]" if target_id else f"'{target_title or 'terbaru'}'"
                date_str = f" pada tanggal {target_date}" if target_date else ""
                return ChatResponse(response=f"🤖 **FinTracks AI Assistant:**\n\nMaaf, saya tidak menemukan transaksi dengan detail {detail_str}{date_str}.")
        else:
            return ChatResponse(response=f"🤖 **FinTracks AI Assistant:**\n\nTidak ada transaksi yang bisa dihapus.")

    # 2. UPDATE: Ubah Transaksi
    if any(k in msg_lower for k in ["ubah", "update", "ganti", "edit", "perbarui"]):
        target_title, target_date = extract_delete_params(user_msg)
        id_match_prompt = re.search(r'\b(?:id|#)\s*(\d+)\b', msg_lower)
        target_id = id_match_prompt.group(1) if id_match_prompt else (target_title if target_title.isdigit() else None)
        amount = parse_amount(user_msg)

        res_tx = call_mcp_tool("get_transactions", {"user_id": user_id, "limit": 50})
        if res_tx:
            matching_tx_id, tx_title_found = find_matching_transaction(
                res_tx,
                target_title="" if target_id else target_title,
                target_date=target_date,
                target_id=target_id
            )
            if matching_tx_id and amount > 0:
                upd_res = call_mcp_tool("update_transaction", {
                    "transaction_id": int(matching_tx_id),
                    "user_id": user_id,
                    "amount": amount
                })
                return ChatResponse(response=f"🤖 **FinTracks AI Assistant:**\n\n{upd_res if upd_res else 'Nominal transaksi berhasil diperbarui.'}")
            elif not matching_tx_id:
                return ChatResponse(response=f"🤖 **FinTracks AI Assistant:**\n\nMaaf, saya tidak menemukan transaksi yang ingin diubah.")
            elif amount <= 0:
                return ChatResponse(response=f"🤖 **FinTracks AI Assistant:**\n\nMohon sebutkan nominal baru untuk transaksi tersebut (contoh: 'ubah nominal ikan bakar jadi 50k').")

    # 3. CREATE: Tambah Transaksi
    if any(k in msg_lower for k in ["catat", "tambah", "pemasukan", "pengeluaran", "bayar", "beli"]):
        tx_type, amount, category, title = extract_transaction_details(user_msg)
        if category == "Lainnya" and amount > 0:
            try:
                ai_cat_prompt = f"Kategorikan transaksi berikut: '{title}'. Pilih satu dari: [Makanan & Minuman, Transportasi, Belanja, Pendapatan, Kesehatan, Hiburan, Tagihan, Lainnya]. Jawab HANYA dengan nama kategorinya saja."
                payload = {
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": ai_cat_prompt}],
                    "stream": False
                }
                res_cat = requests.post(OLLAMA_URL, json=payload, timeout=5)
                if res_cat.status_code == 200:
                    ai_cat = res_cat.json().get("message", {}).get("content", "").strip()
                    valid_cats = ["Makanan & Minuman", "Transportasi", "Belanja", "Pendapatan", "Kesehatan", "Hiburan", "Tagihan", "Lainnya"]
                    if any(vc in ai_cat for vc in valid_cats):
                        category = next((vc for vc in valid_cats if vc in ai_cat), "Lainnya")
            except Exception as e:
                print(f"Category AI Error: {e}")
        if amount > 0:
            from datetime import datetime
            date_str = datetime.now().strftime("%Y-%m-%d")
            mcp_res = call_mcp_tool("create_transaction", {
                "user_id": user_id,
                "title": title,
                "amount": amount,
                "category": category,
                "transaction_type": tx_type,
                "date": date_str,
                "note": "Dicatat via FinTracks AI Chatbot"
            })
            if mcp_res:
                return ChatResponse(response=f"🤖 **FinTracks AI Assistant:**\n\n{mcp_res}")

    # 4. READ: Ringkasan / Saldo
    if any(k in msg_lower for k in ["saldo", "ringkasan", "summary", "total"]):
        mcp_res = call_mcp_tool("get_summary", {"user_id": user_id})
        if mcp_res:
            return ChatResponse(response=f"🤖 **FinTracks AI Assistant:**\n\n{mcp_res}")

    # 5. READ: Riwayat Transaksi
    if any(k in msg_lower for k in ["lihat", "riwayat", "daftar", "list", "tampilkan", "cek transaksi"]) or msg_lower in ["transaksi", "transaksi saya"]:
        mcp_res = call_mcp_tool("get_transactions", {"user_id": user_id, "limit": 10})
        if mcp_res:
            return ChatResponse(response=f"🤖 **FinTracks AI Assistant:**\n\nBerikut transaksi terbaru Anda:\n{mcp_res}")

    # 6. Ollama Fallback
    try:
        system_prompt = f"Anda adalah asisten keuangan pribadi FinTracks untuk User ID {user_id}. Jawablah dengan ramah dalam Bahasa Indonesia."
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            "stream": False,
            "options": {"temperature": 0.7}
        }
        res = requests.post(OLLAMA_URL, json=payload, timeout=10)
        if res.status_code == 200:
            result = res.json()
            ai_msg = result.get("message", {}).get("content")
            if ai_msg:
                return ChatResponse(response=ai_msg)
    except Exception:
        pass

    # 7. Final Fallback
    mcp_res = call_mcp_tool("get_summary", {"user_id": user_id})
    return ChatResponse(response=f"Halo! Saya AI Assistant. Coba katakan 'Cek saldo', 'Hapus transaksi ikan bakar', atau 'Catat makan siang 20k'.\n\n{mcp_res if mcp_res else ''}")

