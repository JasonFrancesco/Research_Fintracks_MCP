import os
import re
import json
import time
import requests
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models.models import User, ChatHistory

router = APIRouter(prefix="/chat", tags=["AI Chatbot"])

class ChatRequest(BaseModel):
    # id preset dari dropdown Chatbot: "local" | "gpt" | "gemma"
    # nilai lama "cloud" masih diterima demi kompatibilitas
    message: str
    model: Optional[str] = "local"

class ChatResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    response: str
    model_used: Optional[str] = None

class ChatMessageItem(BaseModel):
    id: int
    role: str
    text: str
    created_at: Optional[datetime] = None

# Lapisan MCP client: backend bicara ke mcp-server lewat protokol MCP
# (tools/list + tools/call), bukan REST. Menggantikan MCP_SERVER_URL + call_mcp_tool.
from ..mcp import client as mcp_client
from ..mcp.schema_adapter import mcp_tools_to_llm_schema

# Nilai awal sebagai cadangan. JANGAN dipakai langsung untuk request: konstanta
# modul hanya dibaca sekali saat import, sehingga perubahan .env tidak terbaca
# sampai backend di-restart. Gunakan get_ollama_runtime() / get_cloud_timeout().
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30"))
CLOUD_TIMEOUT = float(os.getenv("CLOUD_TIMEOUT", "60"))


def get_ollama_runtime() -> tuple[str, float]:
    """
    Membaca ulang OLLAMA_BASE_URL dan OLLAMA_TIMEOUT dari .env setiap dipanggil,
    supaya ganti model/timeout saat benchmark tidak perlu restart backend.
    Return: (chat_url, timeout_detik)
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)

    base = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").strip().rstrip("/")
    raw_timeout = (os.getenv("OLLAMA_TIMEOUT") or "").strip()
    try:
        timeout = float(raw_timeout) if raw_timeout else 30.0
    except ValueError:
        print(f"[Config] OLLAMA_TIMEOUT='{raw_timeout}' bukan angka. Memakai 30.")
        timeout = 30.0
    return f"{base}/api/chat", timeout


def get_cloud_timeout() -> float:
    from dotenv import load_dotenv
    load_dotenv(override=True)

    raw = (os.getenv("CLOUD_TIMEOUT") or "").strip()
    try:
        return float(raw) if raw else 60.0
    except ValueError:
        print(f"[Config] CLOUD_TIMEOUT='{raw}' bukan angka. Memakai 60.")
        return 60.0

# ---------------------------------------------------------------------------
# Registry Provider Cloud (semuanya memakai format OpenAI Chat Completions)
# ---------------------------------------------------------------------------
CLOUD_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "key_envs": ["GROQ_API_KEY", "CLOUD_API_KEY"],
        "default_model": "openai/gpt-oss-120b",
        "key_page": "https://console.groq.com/keys",
        "supports_tools": True,
    },
    "ollama_cloud": {
        "label": "Ollama Cloud",
        "base_url": "https://ollama.com/v1",
        "key_envs": ["OLLAMA_API_KEY", "CLOUD_API_KEY"],
        "default_model": "gpt-oss:120b",
        "key_page": "https://ollama.com/settings/keys",
        "supports_tools": True,
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "key_envs": ["OPENROUTER_API_KEY", "CLOUD_API_KEY"],
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "key_page": "https://openrouter.ai/keys",
        "supports_tools": True,
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_envs": ["GEMINI_API_KEY", "CLOUD_API_KEY"],
        "default_model": "gemini-2.0-flash",
        "key_page": "https://aistudio.google.com/apikey",
        "supports_tools": True,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "key_envs": ["OPENAI_API_KEY", "CLOUD_API_KEY"],
        "default_model": "gpt-4o-mini",
        "key_page": "https://platform.openai.com/api-keys",
        "supports_tools": True,
    },
}

# Urutan deteksi otomatis ketika CLOUD_PROVIDER tidak diisi
_PROVIDER_SNIFF_ORDER = ["groq", "ollama_cloud", "openrouter", "gemini", "openai"]

# ---------------------------------------------------------------------------
# Preset model yang dipilih user dari dropdown Chatbot.
# Setiap preset mengikat satu provider + satu model, jadi pilihan di UI
# tidak lagi bergantung pada isi CLOUD_PROVIDER di .env.
# ---------------------------------------------------------------------------
CHAT_PRESETS: Dict[str, Dict[str, Any]] = {
    "local": {
        "label": "🖥️ Lokal (Ollama)",
        "mode": "local",
        "provider": None,
        "model": None,              # diambil dari ACTIVE_MODEL
        "model_env": "ACTIVE_MODEL",
        "description": "Model yang berjalan di komputer ini. Gratis, tanpa internet.",
    },
    "gpt": {
        "label": "⚡ GPT-OSS 120B (Groq)",
        "mode": "cloud",
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "model_env": "PRESET_GPT_MODEL",
        "description": "Cepat dan paling andal untuk MCP tool calling.",
    },
    "gemma": {
        "label": "💠 Gemma 4 31B (Ollama Cloud)",
        "mode": "cloud",
        "provider": "ollama_cloud",
        "model": "gemma4:31b",
        "model_env": "PRESET_GEMMA_MODEL",
        "description": "Model Gemma 4 yang di-host Ollama Cloud.",
    },
}

DEFAULT_PRESET = "local"


def resolve_preset(preset_id: Optional[str]) -> Dict[str, Any]:
    """
    Menerjemahkan pilihan dropdown menjadi konfigurasi eksekusi.
    Nilai lama "cloud" tetap didukung: ia mengikuti CLOUD_PROVIDER/CLOUD_MODEL di .env.
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)

    pid = (preset_id or DEFAULT_PRESET).strip().lower()

    if pid == "cloud":
        # Mode legacy: seluruh konfigurasi diambil dari .env
        cfg = resolve_cloud_config()
        return {
            "id": "cloud",
            "label": f"☁️ Cloud ({cfg['label']}: {cfg['model']})",
            "mode": "cloud",
            "provider": cfg["provider"],
            "model": cfg["model"],
            "known": True,
        }

    if pid not in CHAT_PRESETS:
        print(f"[Preset] '{pid}' tidak dikenal. Pilihan valid: {list(CHAT_PRESETS)}. Memakai '{DEFAULT_PRESET}'.")
        pid = DEFAULT_PRESET

    spec = CHAT_PRESETS[pid]
    model = (os.getenv(spec["model_env"]) or "").strip() or spec["model"]

    if spec["mode"] == "local":
        model = get_active_model()

    return {
        "id": pid,
        "label": spec["label"],
        "mode": spec["mode"],
        "provider": spec["provider"],
        "model": model,
        "description": spec["description"],
        "known": True,
    }


def resolve_cloud_config(
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Menentukan provider cloud, endpoint, model, dan API key yang akan dipakai.
    Prioritas provider: argumen preset -> CLOUD_PROVIDER di .env -> deteksi dari
    nama env key yang terisi -> groq.
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)

    if provider_override and provider_override in CLOUD_PROVIDERS:
        requested = provider_override
    else:
        requested = (os.getenv("CLOUD_PROVIDER") or "").strip().lower().replace("-", "_")
    provider = requested if requested in CLOUD_PROVIDERS else None
    if requested and provider is None:
        print(
            f"[Cloud Config] CLOUD_PROVIDER='{requested}' tidak dikenal. "
            f"Pilihan valid: {list(CLOUD_PROVIDERS)}. Beralih ke deteksi otomatis."
        )

    if provider is None:
        # Deteksi dari API key spesifik provider yang terisi (CLOUD_API_KEY tidak dihitung
        # karena generik dan tidak menunjukkan provider mana pun).
        for name in _PROVIDER_SNIFF_ORDER:
            specific_envs = [e for e in CLOUD_PROVIDERS[name]["key_envs"] if e != "CLOUD_API_KEY"]
            if any(os.getenv(e) for e in specific_envs):
                provider = name
                break

    if provider is None:
        provider = "groq"

    spec = CLOUD_PROVIDERS[provider]

    api_key = ""
    key_source = None
    for env_name in spec["key_envs"]:
        val = (os.getenv(env_name) or "").strip()
        if val:
            api_key = val
            key_source = env_name
            break

    # CLOUD_BASE_URL hanya berlaku untuk mode legacy. Preset sudah mengikat provider
    # secara eksplisit, jadi gateway global tidak boleh menimpanya.
    custom_base = "" if provider_override else (os.getenv("CLOUD_BASE_URL") or "").strip()
    base_url = custom_base or spec["base_url"]
    if base_url.endswith("/chat/completions"):
        url = base_url
    else:
        url = f"{base_url.rstrip('/')}/chat/completions"

    if model_override:
        model = model_override
    else:
        model = (os.getenv("CLOUD_MODEL") or "").strip() or spec["default_model"]

    return {
        "provider": provider,
        "label": spec["label"],
        "url": url,
        "model": model,
        "api_key": api_key,
        "key_source": key_source,
        "key_page": spec["key_page"],
        "requested_provider": requested,
        "base_url_overridden": bool(custom_base),
    }


def _mask(key: str) -> str:
    if not key:
        return "(kosong)"
    if len(key) <= 10:
        return f"{key[:3]}...({len(key)} char)"
    return f"{key[:6]}...{key[-4:]} ({len(key)} char)"

def save_chat_message(db: Session, user_id: int, role: str, message: str):
    try:
        chat_item = ChatHistory(user_id=user_id, role=role, message=message)
        db.add(chat_item)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Chat History Error] Failed to save {role} message: {e}")

@router.get("/history", response_model=List[ChatMessageItem])
async def get_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mengambil seluruh riwayat pesan chat milik user"""
    history = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == current_user.id)
        .order_by(ChatHistory.created_at.asc())
        .all()
    )
    return [
        ChatMessageItem(
            id=item.id,
            role=item.role,
            text=item.message,
            created_at=item.created_at
        )
        for item in history
    ]

@router.delete("/history")
async def clear_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Hapus seluruh riwayat percakapan user"""
    db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Riwayat percakapan berhasil dihapus"}

@router.get("/models")
async def get_available_models():
    """
    Mengembalikan daftar preset model untuk dropdown Chatbot.
    Frontend merender opsi dari sini, jadi menambah model cukup di backend.
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)

    options = []
    for pid in CHAT_PRESETS:
        preset = resolve_preset(pid)
        item: Dict[str, Any] = {
            "id": pid,
            "name": preset["label"],
            "model": preset["model"],
            "mode": preset["mode"],
            "description": preset["description"],
        }
        if preset["mode"] == "cloud":
            cfg = resolve_cloud_config(preset["provider"], preset["model"])
            item["provider"] = cfg["provider"]
            item["endpoint"] = cfg["url"]
            item["available"] = bool(cfg["api_key"])
            item["hint"] = (
                None if cfg["api_key"]
                else f"Isi {CLOUD_PROVIDERS[cfg['provider']]['key_envs'][0]} di backend/.env"
            )
        else:
            item["provider"] = "ollama"
            item["endpoint"] = get_ollama_runtime()[0]
            item["available"] = True
            item["hint"] = None
        options.append(item)

    return {"default": DEFAULT_PRESET, "models": options}


@router.get("/diagnose")
async def diagnose_models(
    preset: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Uji koneksi tiap preset tanpa menyentuh riwayat percakapan.
    Tanpa parameter: menguji semua preset. Dengan ?preset=gpt: hanya satu.
    """
    targets = [preset] if preset else list(CHAT_PRESETS)
    results = []

    for pid in targets:
        p = resolve_preset(pid)
        report: Dict[str, Any] = {
            "preset": p["id"],
            "label": p["label"],
            "mode": p["mode"],
            "model": p["model"],
        }

        if p["mode"] == "local":
            local_url, local_timeout = get_ollama_runtime()
            report["endpoint"] = local_url
            try:
                res = requests.post(
                    local_url,
                    json={
                        "model": p["model"],
                        "messages": [{"role": "user", "content": "ping"}],
                        "stream": False,
                    },
                    timeout=local_timeout,
                )
                report["http_status"] = res.status_code
                report["ok"] = res.status_code == 200
                report["detail"] = (
                    "Ollama lokal merespons."
                    if res.status_code == 200
                    else res.text[:300]
                )
            except Exception as e:
                report["ok"] = False
                report["detail"] = f"{type(e).__name__}: {e}. Pastikan Ollama berjalan dan {local_url} dapat diakses."
            results.append(report)
            continue

        cfg = resolve_cloud_config(p["provider"], p["model"])
        report.update({
            "provider": cfg["provider"],
            "endpoint": cfg["url"],
            "key_source": cfg["key_source"],
            "key_preview": _mask(cfg["api_key"]),
        })

        if not cfg["api_key"]:
            report["ok"] = False
            report["detail"] = (
                f"API Key kosong. Isi salah satu dari "
                f"{CLOUD_PROVIDERS[cfg['provider']]['key_envs']} di backend/.env"
            )
            results.append(report)
            continue

        try:
            res = requests.post(
                cfg["url"],
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg["model"],
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
                timeout=get_cloud_timeout(),
            )
            report["http_status"] = res.status_code
            report["ok"] = res.status_code == 200
            report["detail"] = (
                f"Koneksi {cfg['label']} berhasil."
                if res.status_code == 200
                else res.text[:400]
            )
        except Exception as e:
            report["ok"] = False
            report["detail"] = f"{type(e).__name__}: {e}"
        results.append(report)

    return {"results": results}

def get_active_model() -> str:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    raw = os.getenv("ACTIVE_MODEL", "ollama/llama3.2").strip()
    if not raw:
        raw = "ollama/llama3.2"
    return raw.split("/", 1)[1] if "/" in raw else raw

def query_llm(preset_id: str, messages: list, tools: list = None) -> tuple[Optional[dict], Optional[str]]:
    """
    Mengirimkan request ke LLM sesuai preset yang dipilih user di dropdown Chatbot.
    Return: (ai_message_dict, error_string)
    """
    preset = resolve_preset(preset_id)
    mode = preset["mode"]

    if mode == "cloud":
        cfg = resolve_cloud_config(
            provider_override=preset.get("provider"),
            model_override=preset.get("model"),
        )
        url = cfg["url"]
        cloud_model = cfg["model"]
        cloud_api_key = cfg["api_key"]

        if not cloud_api_key:
            envs = " atau ".join(CLOUD_PROVIDERS[cfg["provider"]]["key_envs"])
            return None, (
                f"🤖 **FinTracks AI (Cloud Mode):** API Key belum diisi untuk provider **{cfg['label']}**.\n"
                f"Tambahkan `{envs.split(' atau ')[0]}=...` di `backend/.env`.\n"
                f"Ambil key di: {cfg['key_page']}"
            )

        headers = {
            "Authorization": f"Bearer {cloud_api_key}",
            "Content-Type": "application/json",
        }
        # OpenRouter menganjurkan dua header identifikasi aplikasi ini
        if cfg["provider"] == "openrouter":
            headers["HTTP-Referer"] = "http://localhost:3000"
            headers["X-Title"] = "FinTracks MCP"

        payload: Dict[str, Any] = {
            "model": cloud_model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        cloud_timeout = get_cloud_timeout()
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=cloud_timeout)

            # Sebagian model cloud tidak mendukung function calling -> ulangi tanpa tools
            if res.status_code in (400, 404, 422) and tools:
                low = res.text.lower()
                if "tool" in low or "function" in low:
                    print(f"[Cloud Warning] Model '{cloud_model}' menolak tools, mencoba ulang tanpa tools.")
                    retry_payload = {k: v for k, v in payload.items() if k not in ("tools", "tool_choice")}
                    res = requests.post(url, headers=headers, json=retry_payload, timeout=cloud_timeout)

            if res.status_code in (401, 403):
                return None, (
                    f"🤖 **FinTracks AI (Cloud Auth Error {res.status_code}):**\n"
                    f"• Provider  : **{cfg['label']}** (`CLOUD_PROVIDER={cfg['provider']}`)\n"
                    f"• Endpoint  : `{url}`\n"
                    f"• Key dipakai: `{cfg['key_source'] or '-'}` = {_mask(cloud_api_key)}\n\n"
                    f"Key ini ditolak oleh {cfg['label']}. Buat key baru di {cfg['key_page']}, "
                    f"lalu simpan di `backend/.env` dan kirim ulang pesan (tidak perlu restart backend).\n"
                    f"Pastikan juga `CLOUD_PROVIDER` cocok dengan asal key Anda."
                )

            if res.status_code == 404:
                return None, (
                    f"🤖 **FinTracks AI (Cloud Error 404):** Model `{cloud_model}` tidak ditemukan di **{cfg['label']}**.\n"
                    f"Endpoint: `{url}`\nDetail: {res.text[:300]}\n"
                    f"Perbaiki `CLOUD_MODEL` di `backend/.env`."
                )

            if res.status_code == 429:
                return None, (
                    f"🤖 **FinTracks AI (Rate Limit 429):** Kuota **{cfg['label']}** untuk model "
                    f"`{cloud_model}` sedang penuh. Tunggu sebentar atau ganti `CLOUD_MODEL`.\n"
                    f"Detail: {res.text[:200]}"
                )

            if res.status_code != 200:
                return None, (
                    f"🤖 **FinTracks AI (Cloud Error):** HTTP {res.status_code} dari **{cfg['label']}** "
                    f"model `{cloud_model}`.\nEndpoint: `{url}`\nDetail: {res.text[:400]}"
                )

            data = res.json()
            choices = data.get("choices") or []
            if not choices:
                return None, (
                    f"🤖 **FinTracks AI (Cloud Error):** Respon {cfg['label']} tidak berisi 'choices'.\n"
                    f"Detail: {str(data)[:400]}"
                )

            choice = choices[0].get("message", {}) or {}
            raw_tool_calls = choice.get("tool_calls") or []
            normalized_tool_calls = []
            for tc in raw_tool_calls:
                fn = tc.get("function", {}) or {}
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args.strip() else {}
                    except json.JSONDecodeError:
                        args = {}
                if not isinstance(args, dict):
                    args = {}
                normalized_tool_calls.append({"function": {"name": fn.get("name"), "arguments": args}})

            return {"content": choice.get("content") or "", "tool_calls": normalized_tool_calls}, None

        except requests.exceptions.Timeout:
            return None, (
                f"🤖 **FinTracks AI (Cloud Timeout):** {cfg['label']} tidak merespons dalam {cloud_timeout:.0f}s. "
                f"Naikkan `CLOUD_TIMEOUT` di `backend/.env` atau pakai model yang lebih kecil."
            )
        except Exception as e:
            return None, f"🤖 **FinTracks AI (Cloud Error):** {type(e).__name__}: {str(e)}"


    else:
        # Mode Lokal (Ollama)
        active_model = preset.get("model") or get_active_model()
        payload = {
            "model": active_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2}
        }
        if tools:
            payload["tools"] = tools

        ollama_url, ollama_timeout = get_ollama_runtime()
        try:
            res = requests.post(ollama_url, json=payload, timeout=ollama_timeout)
            if res.status_code == 400 and "does not support tools" in res.text:
                print(f"[Lokal] Model '{active_model}' menolak parameter tools. Mengulang TANPA tools "
                      f"-> MCP tool tidak akan terpanggil untuk pesan ini.")
                fallback_payload = {
                    "model": active_model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.5}
                }
                res = requests.post(ollama_url, json=fallback_payload, timeout=ollama_timeout)

            if res.status_code != 200:
                return None, f"🤖 **FinTracks AI (Lokal Error):** HTTP {res.status_code} dari model '{active_model}'. Coba jalankan 'ollama run {active_model}'."

            res_data = res.json()
            ai_message = res_data.get("message", {})

            # Model reasoning (deepseek-r1, qwen3, dst) mengirim proses berpikirnya
            # di field terpisah. Berguna untuk diagnosa lamanya respons.
            thinking = ai_message.get("thinking") or ""
            if thinking:
                print(f"[Lokal] '{active_model}' adalah model reasoning: {len(thinking)} char proses berpikir "
                      f"(eval_count={res_data.get('eval_count')}). Ini penyebab utama respons lambat.")

            return {"content": ai_message.get("content", "") or "", "tool_calls": ai_message.get("tool_calls", [])}, None

        except requests.exceptions.Timeout:
            return None, (
                f"🤖 **FinTracks AI (Lokal Timeout):** Model '{active_model}' tidak selesai dalam {ollama_timeout:.0f}s.\n"
                f"• Model reasoning seperti `deepseek-r1` butuh 3-5 menit per jawaban di mesin lokal.\n"
                f"• Naikkan `OLLAMA_TIMEOUT` di `backend/.env` (mis. 300), atau pakai model yang lebih ringan."
            )
        except Exception as e:
            return None, f"🤖 **FinTracks AI (Lokal Error):** {type(e).__name__}: {str(e)}"

# CATATAN ARSITEKTUR MCP:
# Daftar tool TIDAK lagi ditulis manual di sini. Dulu ada konstanta TOOLS_SCHEMA
# dan fungsi call_mcp_tool yang menembak REST POST /call. Keduanya dihapus.
# Sekarang backend bertindak sebagai MCP client: skema tool diambil dari server
# via tools/list (app.mcp.client.list_tools) lalu diterjemahkan oleh schema_adapter,
# dan eksekusi tool lewat tools/call (app.mcp.client.call_tool). Server adalah
# satu-satunya sumber kebenaran definisi tool.

# Kata-kata yang tidak layak menjadi judul transaksi: perintah, satuan nominal,
# keterangan waktu, dan preposisi. Dipakai saat model gagal mengirim 'title'.
_TITLE_STOPWORDS = {
    # perintah
    "catat", "catatkan", "tambah", "tambahkan", "tambahin", "masukkan", "masukin",
    "input", "buat", "buatkan", "simpan", "hapus", "ubah", "edit", "update",
    # kata perintah khas update. Tanpa ini, "ubah kopi jadi 30rb" menghasilkan
    # kata kunci "Kopi Jadi" yang tidak akan pernah cocok dengan judul mana pun.
    "jadi", "menjadi", "jd", "ganti", "gantikan", "koreksi", "revisi",
    "perbaiki", "seharusnya", "harusnya",
    # kata generik transaksi
    "transaksi", "pemasukan", "pengeluaran", "income", "expense", "dana", "uang",
    "duit", "saldo", "biaya", "nominal",
    # verba transaksi
    "bayar", "bayarkan", "beli", "membeli", "terima", "dapat", "dapet", "keluar", "masuk",
    # satuan & penanda jumlah
    "sebesar", "sebanyak", "senilai", "sejumlah", "total", "rp", "idr", "rupiah",
    "ribu", "rb", "k", "juta", "jt", "miliar", "milyar",
    # waktu
    "hari", "ini", "kemarin", "tadi", "besok", "tanggal", "tgl", "bulan", "minggu",
    "tahun", "lalu", "barusan", "sekarang",
    # preposisi & partikel
    "dari", "ke", "untuk", "di", "pada", "dengan", "yang", "yg", "dan", "atau",
    "saya", "aku", "punya", "sudah", "baru", "saja",
}


def derive_title_from_message(user_msg: str, category: Optional[str] = None) -> str:
    """
    Menyusun judul transaksi dari pesan user ketika model tidak mengirim 'title'.
    Hanya dipakai sebagai jaring pengaman, bukan jalur utama.
    """
    text = re.sub(r"\d+(?:[.,]\d+)*", " ", user_msg)        # buang semua angka
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)  # buang tanda baca
    words = [w for w in text.split() if w.lower() not in _TITLE_STOPWORDS]

    if not words:
        # Semua kata tersaring, contoh: "tambah dana 5 juta". Kategori lebih informatif
        # daripada judul kosong atau potongan kalimat yang tidak bermakna.
        return category or "Transaksi Baru"

    # Pertahankan kapitalisasi asli bila user sudah menulisnya kapital (nama merek, dll)
    return " ".join(w if w[:1].isupper() else w.capitalize() for w in words[:5])


_MONTHS_ID = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2, "maret": 3, "mar": 3,
    "april": 4, "apr": 4, "mei": 5, "may": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
    "agustus": 8, "agu": 8, "agt": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "oktober": 10, "okt": 10, "oct": 10, "november": 11, "nov": 11,
    "desember": 12, "des": 12, "dec": 12,
}
_MONTH_RE = "|".join(sorted(_MONTHS_ID, key=len, reverse=True))


def _safe_date(year: int, month: int, day: int) -> Optional[datetime]:
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _extract_single_date(user_msg: str, now: datetime) -> Optional[str]:
    """
    Mengambil SATU tanggal eksplisit dari pesan user, format YYYY-MM-DD.
    Mengembalikan None bila tidak ada tanggal atau ada lebih dari satu tanggal berbeda.

    Dikenali: '2026-09-29', '29/09/2026', '29/9', '29 september (2026)',
    'tanggal 29' / 'tgl 29', 'hari ini', 'kemarin'. Angka lepas seperti '50 ribu'
    sengaja tidak dianggap tanggal. Tanggal tanpa bulan/tahun diartikan sebagai
    tanggal terdekat yang sudah lewat, karena pertanyaan riwayat transaksi selalu
    menyangkut masa lalu.
    """
    text = user_msg.lower()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    found = set()

    def most_recent(day: int, month: Optional[int] = None) -> Optional[datetime]:
        if month is None:
            # Bulan ini kalau tanggalnya sudah lewat, selain itu bulan lalu.
            for back in range(0, 3):
                m = today.month - back
                y = today.year
                while m < 1:
                    m += 12
                    y -= 1
                d = _safe_date(y, m, day)
                if d and d <= today:
                    return d
            return None
        d = _safe_date(today.year, month, day)
        if d and d > today:
            d = _safe_date(today.year - 1, month, day)
        return d

    for m in re.finditer(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text):
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            found.add(d)
    for m in re.finditer(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\b", text):
        day, month = int(m.group(1)), int(m.group(2))
        d = _safe_date(int(m.group(3)), month, day) if m.group(3) else most_recent(day, month)
        if d:
            found.add(d)
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({_MONTH_RE})\b\.?(?:\s+(\d{{4}}))?", text):
        day, month = int(m.group(1)), _MONTHS_ID[m.group(2)]
        d = _safe_date(int(m.group(3)), month, day) if m.group(3) else most_recent(day, month)
        if d:
            found.add(d)
    for m in re.finditer(rf"\b(?:tanggal|tgl)\.?\s+(\d{{1,2}})\b(?!\s*(?:{_MONTH_RE})\b)(?![/-]\d)", text):
        d = most_recent(int(m.group(1)))
        if d:
            found.add(d)
    if re.search(r"\bhari ini\b", text):
        found.add(today)
    if re.search(r"\bkemarin\b", text):
        found.add(today - timedelta(days=1))

    if len(found) == 1:
        return next(iter(found)).strftime("%Y-%m-%d")
    return None


# Kata yang menandakan pengguna meminta rentang tanggal, bukan satu hari.
_RANGE_WORDS = re.compile(r"\b(sampai|hingga|s\.?d\.?|sd|antara|dari|sejak|selama|minggu|bulan)\b")


def _extract_tx_type(user_msg: str) -> Optional[str]:
    """'expense'/'income' bila pesan menyebut tepat satu jenis transaksi, selain itu None."""
    text = user_msg.lower()
    is_expense = bool(re.search(r"\b(pengeluaran|expense)\b", text))
    is_income = bool(re.search(r"\b(pemasukan|pendapatan|income)\b", text))
    if is_expense and not is_income:
        return "expense"
    if is_income and not is_expense:
        return "income"
    return None


def sanitize_tool_args(tool_name: str, args: dict, user_id: int, user_msg: str) -> dict:
    """Sanitasi dan melengkapi argumen tool sebelum dikirim ke MCP Server"""
    args["user_id"] = user_id
    today_str = datetime.now().strftime("%Y-%m-%d")

    if tool_name == "create_transaction":
        # Urutan penting: kategori ditentukan lebih dulu agar bisa dipakai sebagai
        # cadangan judul ketika seluruh kata pada pesan user tersaring habis.
        if "amount" in args and args["amount"] is not None:
            try:
                args["amount"] = float(args["amount"])
            except (ValueError, TypeError):
                args["amount"] = 0.0
        else:
            args["amount"] = 0.0

        if "date" not in args or not args["date"]:
            args["date"] = today_str

        msg_lower = user_msg.lower()

        if "transaction_type" not in args or args["transaction_type"] not in ["income", "expense"]:
            args["transaction_type"] = "income" if any(
                k in msg_lower for k in ["gaji", "terima", "masuk", "bonus", "pemasukan"]
            ) else "expense"

        valid_cats = ["Makanan & Minuman", "Transportasi", "Belanja", "Pendapatan", "Kesehatan", "Hiburan", "Tagihan", "Lainnya"]
        if "category" not in args or not args["category"] or args["category"] not in valid_cats:
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

        # Judul terakhir: hanya disusun sendiri bila model benar-benar tidak mengirimnya
        if "title" not in args or not str(args.get("title") or "").strip():
            args["title"] = derive_title_from_message(user_msg, args["category"])
            print(f"[Sanitize] Model tidak mengirim 'title'. Judul disusun dari pesan user -> {args['title']!r}")
        else:
            args["title"] = re.sub(r"\s+", " ", str(args["title"])).strip()

    elif tool_name == "get_transactions":
        if "limit" not in args or not args["limit"]:
            args["limit"] = 10
        else:
            try:
                args["limit"] = int(args["limit"])
            except (ValueError, TypeError):
                args["limit"] = 10

        # Model kecil sering mengirim filter kosong ("", null, "none") untuk parameter
        # yang tidak relevan. Dibuang agar tool memakai default "tanpa filter", bukan
        # menolak string kosong sebagai tanggal yang tidak valid.
        for key in ("start_date", "end_date", "transaction_type"):
            if key in args:
                val = str(args[key] or "").strip()
                if not val or val.lower() in ("none", "null", "all", "semua"):
                    args.pop(key)
                else:
                    args[key] = val

        # Model 3B sering salah mengubah tanggal di pesan menjadi parameter. Teramati
        # pada llama3.2:3b: "tanggal 29" -> tanggal hari ini atau 29 bulan depan, dan
        # "tanggal 30" -> rentang dari hari ini sampai tanggal 30. Jika pesan user
        # memuat TEPAT satu tanggal dan tidak memakai kata rentang, filter dipaksa ke
        # hari itu. Nilai asli model tetap tercatat di log [BENCHMARK] RAW, jadi
        # penilaian kemampuan model tidak ikut "terbantu".
        explicit = _extract_single_date(user_msg, datetime.now())
        if explicit and not _RANGE_WORDS.search(user_msg.lower()):
            if args.get("start_date") != explicit or args.get("end_date") not in (None, explicit):
                print(f"[Sanitize] Tanggal di pesan user = {explicit}, model mengirim "
                      f"start_date={args.get('start_date')!r} end_date={args.get('end_date')!r}. "
                      f"Dikoreksi ke satu hari {explicit}.")
            args["start_date"] = explicit
            args.pop("end_date", None)

        # Jenis transaksi: teramati model mengirim 'expense' untuk pertanyaan
        # "pemasukan tanggal 29". Bila pesan menyebut tepat satu jenis, itu yang dipakai.
        msg_type = _extract_tx_type(user_msg)
        if msg_type and args.get("transaction_type") != msg_type:
            print(f"[Sanitize] Jenis di pesan user = {msg_type}, model mengirim "
                  f"transaction_type={args.get('transaction_type')!r}. Dikoreksi.")
            args["transaction_type"] = msg_type

    elif tool_name == "update_transaction":
        # ID yang tidak valid dibuang, bukan dibiarkan. Jika ID bernilai None atau 0
        # tetap terkirim, MCP akan menganggapnya sebagai selector dan mengabaikan
        # match_title/match_date yang sebetulnya benar.
        raw_id = args.get("transaction_id")
        args.pop("transaction_id", None)
        if raw_id is not None and str(raw_id).strip() != "":
            try:
                parsed_id = int(raw_id)
                if parsed_id > 0:
                    args["transaction_id"] = parsed_id
                else:
                    print(f"[Sanitize] transaction_id={raw_id!r} tidak masuk akal, diabaikan.")
            except (ValueError, TypeError):
                print(f"[Sanitize] transaction_id={raw_id!r} bukan angka, diabaikan.")

        for key in ("match_title", "match_date"):
            if key in args:
                cleaned = re.sub(r"\s+", " ", str(args[key] or "")).strip()
                if cleaned:
                    args[key] = cleaned
                else:
                    args.pop(key)

        # Jaring pengaman: model kadang memanggil update tanpa menyertakan satu pun
        # selector. Kata kunci dari pesan user dipakai sebagai match_title, dan ini
        # aman karena MCP hanya mengeksekusi bila kandidatnya tepat satu.
        if not any(k in args for k in ("transaction_id", "match_title", "match_date")):
            derived = derive_title_from_message(user_msg)
            if derived and derived != "Transaksi Baru":
                args["match_title"] = derived
                print(f"[Sanitize] update_transaction tanpa selector. match_title disusun dari pesan user -> {derived!r}")

    elif tool_name == "delete_transaction":
        if "transaction_id" in args and args["transaction_id"] is not None:
            try:
                args["transaction_id"] = int(args["transaction_id"])
            except (ValueError, TypeError):
                pass

    return args

@router.post("/", response_model=ChatResponse)
async def chat_with_ai(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Endpoint POST /chat/. Ini "otak" alur: menerima pesan dari Chatbot.jsx,
    # mengorkestrasi LLM + MCP, lalu mengembalikan jawaban akhir.
    # current_user sudah diisi oleh get_current_user (hasil verifikasi token JWT).
    user_msg = request.message.strip()         # teks pesan pengguna
    user_id = current_user.id                  # pemilik data; TIDAK diambil dari input mentah
    preset = resolve_preset(request.model)     # terjemahkan 'local'/'gpt'/'gemma' -> konfigurasi model
    model_mode = preset["id"]
    model_label = f"{preset['id']} ({preset['model']})"
    today_str = datetime.now().strftime("%Y-%m-%d")

    # 1. Simpan pesan user ke database (untuk riwayat & memory percakapan)
    save_chat_message(db, user_id, "user", user_msg)

    # 2. Ambil riwayat percakapan sebelumnya untuk konteks memory AI (maks 10 pesan terakhir)
    past_history = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(10)
        .all()
    )
    past_history.reverse()

    system_prompt = (
        f"Anda adalah FinTracks AI Assistant, asisten keuangan pribadi yang cerdas.\n"
        f"User ID: {user_id}. Tanggal hari ini: {today_str}.\n"
        f"Anda memiliki akses ke MCP Tools untuk mengelola data keuangan pengguna:\n"
        f"- create_transaction: Mencatat transaksi baru (pemasukan/pengeluaran).\n"
        f"- get_transactions: Melihat riwayat transaksi. Jika pengguna menyebut tanggal atau "
        f"jenis (pemasukan/pengeluaran), WAJIB isi start_date/end_date dan transaction_type. "
        f"Jika pengguna menyebut tanggal tanpa bulan (contoh 'tanggal 29'), pakai tanggal 29 "
        f"terdekat yang SUDAH LEWAT dari hari ini, jangan tanggal di masa depan.\n"
        f"- get_summary: Melihat ringkasan pemasukan, pengeluaran, dan saldo.\n"
        f"- update_transaction: Mengubah transaksi yang sudah ada.\n"
        f"- delete_transaction: Menghapus transaksi.\n\n"
        f"ATURAN KETAT PENGGUNAAN TOOL:\n"
        f"1. JANGAN PERNAH memanggil 'create_transaction' jika pengguna hanya BERTANYA, BERKONSULTASI, meminta kalkulasi, atau bertanya hipotetis (contoh: 'berapa pemasukan yang harus saya dapatkan...', 'bagaimana menutupi utang').\n"
        f"2. Panggil 'create_transaction' HANYA JIKA pengguna secara EKSPLISIT memerintahkan untuk MENCATAT/INPUT transaksi baru (contoh perintah: 'catat...', 'tambah...', 'saya baru saja beli...', 'masukkan pengeluaran...').\n"
        f"3. Jika pengguna bertanya tentang kondisi keuangan atau analisis saldo/utang, gunakan 'get_summary' atau 'get_transactions' untuk memeriksa data tanpa menambah transaksi baru.\n"
        f"4. Untuk 'update_transaction', pengguna TIDAK perlu menyebut ID. Jika ID tidak diketahui, "
        f"isi 'match_title' dengan kata kunci judul transaksi dan/atau 'match_date' dengan tanggalnya, "
        f"lalu kirim nilai barunya pada parameter yang sesuai. Contoh: 'ubah transaksi kopi jadi 30rb' "
        f"menjadi match_title='kopi' dan amount=30000. Jangan pernah menebak angka ID.\n"
        f"5. Jika hasil 'update_transaction' berisi beberapa kandidat transaksi, sampaikan daftar kandidat "
        f"beserta ID-nya kepada pengguna dan minta pengguna memilih. Jangan mengulang update dengan ID tebakan.\n"
        f"6. Jawablah dengan bahasa Indonesia yang ramah, sopan, dan jelas."
        f"7. AI Models harus pintar dan jelas dalam memutuskan tool mana yang dipanggil kemudian harus menjawab dengan jelas."
    )


    # Susun daftar pesan untuk LLM: system prompt dulu, lalu riwayat lama,
    # terakhir pesan user saat ini. Format {role, content} ini standar chat LLM.
    messages = [{"role": "system", "content": system_prompt}]
    for rec in past_history[:-1]:  # [:-1] = kecualikan pesan user terakhir (ditambah manual di bawah)
        o_role = "user" if rec.role == "user" else "assistant"
        messages.append({"role": o_role, "content": rec.message})

    messages.append({"role": "user", "content": user_msg})

    # Step 0: Ambil daftar tool DARI server MCP via tools/list, lalu terjemahkan
    # ke format function-calling LLM. Inilah inti arsitektur MCP: server adalah
    # sumber kebenaran tool, bukan konstanta di backend.
    try:
        mcp_tools = await mcp_client.list_tools()
        tools_schema = mcp_tools_to_llm_schema(mcp_tools)
    except Exception as e:
        # Server MCP mati/putus: jangan crash. LLM tetap bisa menjawab percakapan
        # umum tanpa tool, dan error-nya transparan di log.
        print(f"[MCP] Gagal mengambil daftar tool dari server MCP: {type(e).__name__}: {e}")
        tools_schema = []

    # Step 1: Panggil LLM RONDE 1 = tahap KEPUTUSAN.
    # LLM melihat pesan + daftar tool, lalu memutuskan: jawab langsung, atau
    # panggil tool tertentu dengan argumen apa.
    print(f"\n{'=' * 78}\n[BENCHMARK] preset={model_label} | history={len(messages) - 2} pesan | tools={len(tools_schema)}\n[BENCHMARK] prompt: {user_msg!r}")
    t_start = time.perf_counter()  # mulai hitung waktu untuk log BENCHMARK
    ai_resp, err_msg = query_llm(model_mode, messages, tools_schema)
    t_decide = time.perf_counter() - t_start

    # Kalau LLM gagal dihubungi (timeout, API key salah, dll), hentikan di sini.
    if err_msg:
        print(f"[BENCHMARK] GAGAL setelah {t_decide:.1f}s: {err_msg.splitlines()[0]}")
        save_chat_message(db, user_id, "ai", err_msg)
        return ChatResponse(response=err_msg, model_used=model_label)

    # tool_calls = daftar tool yang diminta LLM. Kosong = LLM mau jawab langsung.
    tool_calls = ai_resp.get("tool_calls", [])
    print(f"[BENCHMARK] keputusan dalam {t_decide:.1f}s | jumlah tool_calls={len(tool_calls)}")
    if not tool_calls:
        print("[BENCHMARK] tool dipilih: (tidak ada, dijawab langsung)")

    # Step 2: LLM memutuskan memanggil tool -> jalankan tool-nya lewat MCP.
    if tool_calls:
        tool_outputs = []

        # LLM bisa meminta lebih dari satu tool; proses satu per satu.
        for idx, tool_call in enumerate(tool_calls, start=1):
            fn_name = tool_call.get("function", {}).get("name")       # nama tool, mis. "get_transactions"
            fn_args = tool_call.get("function", {}).get("arguments", {})  # argumen pilihan LLM

            # RAW ARGS = output murni model sebelum ditambal sanitize_tool_args.
            # Inilah data yang dipakai untuk menilai kecerdasan model apa adanya.
            print(f"[BENCHMARK]   tool #{idx}: {fn_name}")
            print(f"[BENCHMARK]     RAW dari model : {json.dumps(fn_args, ensure_ascii=False, default=str)}")

            # Perbaiki & lengkapi argumen: suntik user_id, koreksi tanggal/jenis
            # yang sering salah pada model kecil. (lihat fungsi sanitize_tool_args)
            sanitized_args = sanitize_tool_args(fn_name, fn_args, user_id, user_msg)
            print(f"[BENCHMARK]     setelah sanitize: {json.dumps(sanitized_args, ensure_ascii=False, default=str)}")

            # Eksekusi tool di server MCP lewat protokol MCP (tools/call), bukan REST.
            # Di dalam sinilah query/update ke database PostgreSQL terjadi.
            try:
                mcp_result = await mcp_client.call_tool(fn_name, sanitized_args)
            except Exception as e:
                # Server MCP mati/putus: beri pesan, jangan sampai request crash.
                print(f"[MCP] Gagal memanggil tool '{fn_name}': {type(e).__name__}: {e}")
                mcp_result = f"Gagal terhubung ke MCP Server saat memanggil '{fn_name}': {e}"
            print(f"[BENCHMARK]     hasil MCP      : {str(mcp_result)[:160]}")
            tool_outputs.append(str(mcp_result or "Operasi MCP selesai."))

        if len(tool_outputs) > 1:
            print(f"[BENCHMARK]   PERHATIAN: {len(tool_outputs)} tool dieksekusi, "
                  f"tapi hanya hasil tool #1 yang dikirim ke tahap sintesis.")

        # Step 3: Panggil LLM RONDE 2 = tahap SINTESIS.
        # Hasil mentah dari tool (mis. "Ditemukan 2 pemasukan...") diubah jadi
        # kalimat yang ramah dan enak dibaca. Catatan: hanya hasil tool PERTAMA
        # (tool_outputs[0]) yang dikirim ke tahap ini.
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

        # Ronde 2 tidak diberi daftar tool, jadi LLM murni merangkai kalimat.
        synth_resp, _ = query_llm(model_mode, synthesis_messages)
        print(f"[BENCHMARK] total waktu {time.perf_counter() - t_start:.1f}s (keputusan + eksekusi + sintesis)\n{'=' * 78}")
        if synth_resp and synth_resp.get("content"):
            final_ai_msg = synth_resp["content"]
            save_chat_message(db, user_id, "ai", final_ai_msg)  # simpan jawaban ke riwayat
            return ChatResponse(response=final_ai_msg, model_used=model_label)  # <-- balik ke frontend

        # Cadangan: kalau sintesis gagal, tampilkan saja hasil mentah tool apa adanya.
        fallback_ai_msg = f"🤖 **FinTracks AI Assistant:**\n\n" + "\n\n".join(tool_outputs)
        save_chat_message(db, user_id, "ai", fallback_ai_msg)
        return ChatResponse(response=fallback_ai_msg, model_used=model_label)

    # Step 4: LLM tidak butuh tool (sapaan / pertanyaan umum) -> pakai jawaban ronde 1.
    direct_response = ai_resp.get("content", "")
    if direct_response:
        save_chat_message(db, user_id, "ai", direct_response)
        return ChatResponse(response=direct_response, model_used=model_label)

    # Pengaman terakhir: LLM tidak memanggil tool DAN tidak memberi teks apa pun.
    empty_ai_msg = "🤖 **FinTracks AI Assistant:** Maaf, saya tidak dapat memahami permintaan Anda."
    save_chat_message(db, user_id, "ai", empty_ai_msg)
    return ChatResponse(response=empty_ai_msg, model_used=model_label)



