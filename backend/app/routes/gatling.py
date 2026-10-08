import os
import re
import json
import time
import requests
import urllib3
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models.models import User, GatlingTestRun, GatlingChatHistory
from ..mcp import client as mcp_client
from ..mcp.schema_adapter import mcp_tools_to_llm_schema
from ..services.gatling_report_generator import generate_gatling_html_report
from .chat import query_llm, resolve_preset

router = APIRouter(prefix="/gatling", tags=["Gatling & RabbitMQ"])


# --- Pydantic Schemas ---
class GatlingChatRequest(BaseModel):
    message: str
    model: Optional[str] = "gemini"


class GatlingChatResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    response: str
    model_used: Optional[str] = None


class GatlingChatMessageItem(BaseModel):
    id: int
    role: str
    text: str
    created_at: Optional[datetime] = None


class GatlingTestRunOut(BaseModel):
    id: int
    simulation_name: str
    scenario_description: Optional[str] = None
    target_queue: str
    virtual_users: int
    duration_seconds: int
    status: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    mean_response_time: float
    p95_response_time: float
    p99_response_time: float
    error_rate: float
    report_url: Optional[str] = None
    report_summary: Optional[str] = None
    generated_script: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TriggerTestRequest(BaseModel):
    simulation_name: str
    target_queue: str
    virtual_users: Optional[int] = 100
    duration_seconds: Optional[int] = 30
    scenario_description: Optional[str] = None
    login_username: Optional[str] = None
    login_password: Optional[str] = None
    login_captcha: Optional[str] = None


def save_gatling_chat_message(db: Session, user_id: int, role: str, message: str):
    try:
        item = GatlingChatHistory(user_id=user_id, role=role, message=message)
        db.add(item)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Gatling History Error] Failed to save {role} message: {e}")


# --- Gatling History Endpoints ---
@router.get("/history", response_model=List[GatlingTestRunOut])
def get_gatling_test_history(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mengambil riwayat eksekusi pengujian Gatling milik user."""
    runs = (
        db.query(GatlingTestRun)
        .filter(GatlingTestRun.user_id == current_user.id)
        .order_by(GatlingTestRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return runs


@router.get("/test/{test_id}", response_model=GatlingTestRunOut)
def get_gatling_test_detail(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mengambil rincian laporan dan skrip uji beban Gatling."""
    run = (
        db.query(GatlingTestRun)
        .filter(GatlingTestRun.id == test_id, GatlingTestRun.user_id == current_user.id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run


@router.get("/report/{test_id}/html", response_class=HTMLResponse)
def get_gatling_html_report_view(
    test_id: int,
    db: Session = Depends(get_db)
):
    """
    Menampilkan berkas HTML resmi Gatling Report secara mandiri.
    Dapat dibuka langsung di tab baru browser atau di dalam iframe.
    """
    run = db.query(GatlingTestRun).filter(GatlingTestRun.id == test_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    report_file_path = os.path.join(reports_dir, f"gatling_report_{test_id}.html")

    needs_generation = True
    if os.path.exists(report_file_path):
        with open(report_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        if "/gatling-assets/" in html_content and "onglet" in html_content:
            needs_generation = False

    if needs_generation:
        summary = json.loads(run.report_summary) if run.report_summary else {}
        html_content = generate_gatling_html_report(
            test_id=run.id,
            simulation_name=run.simulation_name,
            target=run.target_queue,
            virtual_users=run.virtual_users,
            duration_seconds=run.duration_seconds,
            total_requests=run.total_requests,
            successful_requests=run.successful_requests,
            failed_requests=run.failed_requests,
            mean_rt=float(run.mean_response_time or 0),
            p95_rt=float(run.p95_response_time or 0),
            p99_rt=float(run.p99_response_time or 0),
            error_rate=float(run.error_rate or 0),
            report_summary=summary,
            generated_script=run.generated_script,
            created_at=run.created_at
        )
        with open(report_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    return HTMLResponse(content=html_content)


@router.get("/report/{test_id}/download")
def download_gatling_html_report(
    test_id: int,
    db: Session = Depends(get_db)
):
    """
    Mengunduh berkas laporan Gatling resmi (.html).
    """
    run = db.query(GatlingTestRun).filter(GatlingTestRun.id == test_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    report_file_path = os.path.join(reports_dir, f"gatling_report_{test_id}.html")

    needs_generation = True
    if os.path.exists(report_file_path):
        with open(report_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        if "/gatling-assets/" in html_content and "onglet" in html_content:
            needs_generation = False

    if needs_generation:
        summary = json.loads(run.report_summary) if run.report_summary else {}
        html_content = generate_gatling_html_report(
            test_id=run.id,
            simulation_name=run.simulation_name,
            target=run.target_queue,
            virtual_users=run.virtual_users,
            duration_seconds=run.duration_seconds,
            total_requests=run.total_requests,
            successful_requests=run.successful_requests,
            failed_requests=run.failed_requests,
            mean_rt=float(run.mean_response_time or 0),
            p95_rt=float(run.p95_response_time or 0),
            p99_rt=float(run.p99_response_time or 0),
            error_rate=float(run.error_rate or 0),
            report_summary=summary,
            generated_script=run.generated_script,
            created_at=run.created_at
        )
        with open(report_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', run.simulation_name)
    filename = f"gatling_report_{clean_name}_{test_id}.html"

    # Untuk standalone file yang dibuka via file://, arahkan asset ke http://localhost:8000/gatling-assets/
    standalone_html = html_content.replace('href="/gatling-assets/', 'href="http://localhost:8000/gatling-assets/')
    standalone_html = standalone_html.replace('src="/gatling-assets/', 'src="http://localhost:8000/gatling-assets/')

    return Response(
        content=standalone_html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/report/{test_id}/download-zip")
def download_gatling_zip_bundle(
    test_id: int,
    db: Session = Depends(get_db)
):
    """
    Mengunduh bundle lengkap laporan Gatling berupa berkas .zip
    (berisi index.html, style/, dan js/) yang siap diekstrak dan dibuka offline
    persis seperti output bawaan Gatling CLI.
    """
    import zipfile
    import io

    run = db.query(GatlingTestRun).filter(GatlingTestRun.id == test_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    summary = json.loads(run.report_summary) if run.report_summary else {}
    html_content = generate_gatling_html_report(
        test_id=run.id,
        simulation_name=run.simulation_name,
        target=run.target_queue,
        virtual_users=run.virtual_users,
        duration_seconds=run.duration_seconds,
        total_requests=run.total_requests,
        successful_requests=run.successful_requests,
        failed_requests=run.failed_requests,
        mean_rt=float(run.mean_response_time or 0),
        p95_rt=float(run.p95_response_time or 0),
        p99_rt=float(run.p99_response_time or 0),
        error_rate=float(run.error_rate or 0),
        report_summary=summary,
        generated_script=run.generated_script,
        created_at=run.created_at
    )
    # Kembalikan relative paths style/ dan js/ untuk format zip offline
    offline_html = html_content.replace('href="/gatling-assets/', 'href="')
    offline_html = offline_html.replace('src="/gatling-assets/', 'src="')

    gatling_template_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "gatling_template"
    )

    zip_buffer = io.BytesIO()
    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', run.simulation_name).lower()
    folder_prefix = f"{clean_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(f"{folder_prefix}/index.html", offline_html)

        # Masukkan style/ dan js/
        for subfolder in ["style", "js"]:
            subfolder_path = os.path.join(gatling_template_dir, subfolder)
            if os.path.exists(subfolder_path):
                for root, _, files in os.walk(subfolder_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, gatling_template_dir)
                        zip_file.write(full_path, arcname=f"{folder_prefix}/{rel_path}")

    zip_buffer.seek(0)
    zip_filename = f"{folder_prefix}.zip"

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    )


@router.delete("/test/{test_id}")
def delete_gatling_test_run(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Menghapus catatan hasil uji beban Gatling tertentu."""
    run = (
        db.query(GatlingTestRun)
        .filter(GatlingTestRun.id == test_id, GatlingTestRun.user_id == current_user.id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    db.delete(run)
    db.commit()
    return {"message": "Test run deleted successfully", "id": test_id}


@router.get("/ping-target")
def ping_target_endpoint(
    url: str = Query(..., description="Target URL atau host yang ingin diuji"),
    current_user: User = Depends(get_current_user),
):
    """Memeriksa apakah target URL (seperti https://192.168.18.57:44396/) online dan mengukur live latency."""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    start = time.time()
    try:
        res = requests.get(url, verify=False, timeout=3.5, allow_redirects=True)
        elapsed_ms = round((time.time() - start) * 1000, 1)
        return {
            "online": True,
            "url": url,
            "status_code": res.status_code,
            "latency_ms": elapsed_ms,
            "server": res.headers.get("Server", "Unknown Server"),
            "message": f"Online (Status {res.status_code}) ~{elapsed_ms}ms"
        }
    except Exception as e:
        elapsed_ms = round((time.time() - start) * 1000, 1)
        return {
            "online": False,
            "url": url,
            "status_code": None,
            "latency_ms": elapsed_ms,
            "server": None,
            "error": str(e),
            "message": f"Offline / Timeout: {str(e)[:60]}"
        }


@router.post("/trigger", response_model=GatlingTestRunOut)
async def trigger_manual_gatling_test(
    payload: TriggerTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Memicu pengujian beban Gatling langsung via API REST."""
    args = {
        "user_id": current_user.id,
        "simulation_name": payload.simulation_name or "TargetStressTest",
        "target_queue": payload.target_queue,
        "virtual_users": payload.virtual_users or 100,
        "duration_seconds": payload.duration_seconds or 30,
        "scenario_description": payload.scenario_description,
        "login_username": payload.login_username,
        "login_password": payload.login_password,
        "login_captcha": payload.login_captcha,
    }
    try:
        await mcp_client.call_tool("trigger_gatling_test", args)
    except Exception as e:
        print(f"[Gatling Manual Trigger Error]: {e}")

    # Ambil record terbaru yang baru saja dibuat
    latest = (
        db.query(GatlingTestRun)
        .filter(GatlingTestRun.user_id == current_user.id)
        .order_by(GatlingTestRun.id.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=500, detail="Failed to record test run")
    return latest


# --- Gatling Chat Endpoints ---
@router.get("/chat/history", response_model=List[GatlingChatMessageItem])
def get_gatling_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mengambil riwayat percakapan sesi Gatling & RabbitMQ."""
    history = (
        db.query(GatlingChatHistory)
        .filter(GatlingChatHistory.user_id == current_user.id)
        .order_by(GatlingChatHistory.created_at.asc())
        .all()
    )
    return [
        GatlingChatMessageItem(id=h.id, role=h.role, text=h.message, created_at=h.created_at)
        for h in history
    ]


@router.delete("/chat/history")
def clear_gatling_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Menghapus riwayat percakapan sesi Gatling."""
    db.query(GatlingChatHistory).filter(GatlingChatHistory.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Riwayat percakapan Gatling berhasil dihapus"}


@router.post("/chat", response_model=GatlingChatResponse)
async def chat_with_gatling_ai(
    request: GatlingChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI Chatbot khusus Performance Engineering, Gatling Load Testing, dan RabbitMQ Queue Management.
    """
    user_msg = request.message.strip()
    user_id = current_user.id
    preset = resolve_preset(request.model or "gemini")
    model_mode = preset["id"]
    model_label = f"{preset['id']} ({preset['model']})"

    # Simpan pesan user
    save_gatling_chat_message(db, user_id, "user", user_msg)

    # Ambil 10 pesan riwayat chat Gatling terakhir
    past = (
        db.query(GatlingChatHistory)
        .filter(GatlingChatHistory.user_id == user_id)
        .order_by(GatlingChatHistory.created_at.desc())
        .limit(10)
        .all()
    )
    past.reverse()

    system_prompt = (
        f"Anda adalah FinTracks Performance Testing & Gatling Specialist AI Assistant.\n"
        f"User ID: {user_id}. Anda adalah pakar dalam Performance Engineering, Uji Beban (Stress Testing & Load Testing) Gatling, serta RabbitMQ Message Broker.\n\n"
        f"TARGET PENGUJIAN UTAMA PENGGUNA:\n"
        f"• Target Endpoint URL: `https://192.168.18.57:44396/` (Aplikasi IIS / ASP.NET / IdentityServer3 e-Procurement Mandiri Tunas Finance yang berjalan di laptop pengguna, port HTTPS 44396).\n"
        f"• UJI BEBAN DENGAN LOGIN / AUTENTIKASI: DIDUKUNG PENUH (100% BISA).\n"
        f"  - Parameter login yang tersedia: Username='manager_mark', Password='Admin123', Captcha='abc'.\n"
        f"  - Arsitektur login: IdentityServer3 OpenID Connect (OIDC). Form POST mengekstrak anti-forgery token (idsrv.xsrf) dan dynamic captcha GUID dari modelJson, lalu memformat username: `manager_mark#abc#{{captchaGuid}}`. Setelah POST login berhasil (HTTP 302), server mengarahkan ke authorize callback dan menerbitkan `.AspNet.Cookies` session cookies.\n"
        f"• RabbitMQ Broker: Dijalankan lokal di laptop pengguna (host localhost:5672 atau antrean seperti fintracks.orders, fintracks.transactions).\n\n"
        f"Anda memiliki akses ke MCP Tools khusus Gatling & RabbitMQ:\n"
        f"1. generate_gatling_script: Menghasilkan skrip simulasi Gatling (Scala DSL). Mampu menangani target URL HTTP/HTTPS biasa, pengujian login terotentikasi (dengan login_username, login_password, login_captcha), maupun antrean AMQP RabbitMQ.\n"
        f"2. trigger_gatling_test: Memicu eksekusi simulasi pengujian beban (termasuk skenario login jika login_username & login_password diberikan) dan mencatat hasilnya (latency, p95/p99, throughput, error rate) ke database.\n"
        f"3. get_gatling_history: Melihat riwayat pengujian beban yang pernah dilakukan pengguna.\n"
        f"4. get_gatling_report: Melihat detail metrik dan analisis laporan pengujian tertentu berdasarkan ID.\n"
        f"5. get_rabbitmq_queue_status: Memeriksa metrik atau ketersediaan antrean RabbitMQ.\n\n"
        f"PRINSIP EKSEKUSI NYATA & INTEGRASI GATLING:\n"
        f"• Jika pengguna bertanya 'apakah bisa test pakai login?' atau memberikan username/pass/captcha, konfirmasi dengan antusias dan jelas bahwa BISA SEKALI (100% didukung). Jelaskan alur OIDC handshake, token extraction, dan format username kompositnya.\n"
        f"• Jika pengguna meminta 'jalankan test', 'uji URL', 'test login', selalu panggil 'trigger_gatling_test' dengan target_queue='https://192.168.18.57:44396/' dan sertakan login_username='manager_mark', login_password='Admin123', login_captcha='abc' bila relevan.\n"
        f"• Mesin Gatling mengeksekusi uji beban secara nyata selama durasi penuh (misalnya 20 detik penuh).\n"
        f"• Setelah tool selesai dieksekusi, sajikan laporan akhir secara profesional, ramah, dan transparan dalam Bahasa Indonesia."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for rec in past[:-1]:
        messages.append({"role": "user" if rec.role == "user" else "assistant", "content": rec.message})
    messages.append({"role": "user", "content": user_msg})

    # Ambil tools dari MCP server
    try:
        mcp_tools = await mcp_client.list_tools()
        tools_schema = mcp_tools_to_llm_schema(mcp_tools)
    except Exception as e:
        print(f"[MCP Gatling Error] tools/list: {e}")
        tools_schema = []

    # Ronde 1: Keputusan LLM
    ai_resp, err_msg = query_llm(model_mode, messages, tools_schema)
    if err_msg:
        save_gatling_chat_message(db, user_id, "ai", err_msg)
        return GatlingChatResponse(response=err_msg, model_used=model_label)

    tool_calls = ai_resp.get("tool_calls", [])

    if tool_calls:
        tool_outputs = []
        for tc in tool_calls:
            fn_name = tc.get("function", {}).get("name")
            fn_args = tc.get("function", {}).get("arguments", {})

            # Suntikkan user_id ke tool yang membutuhkannya
            if fn_name in ("trigger_gatling_test", "get_gatling_history", "get_gatling_report"):
                fn_args["user_id"] = user_id

            try:
                res = await mcp_client.call_tool(fn_name, fn_args)
                tool_outputs.append(str(res))
            except Exception as e:
                tool_outputs.append(f"Error memanggil tool '{fn_name}': {e}")

        # Ronde 2: Sintesis
        synthesis_messages = [
            {
                "role": "system",
                "content": (
                    "Anda adalah FinTracks Performance Testing & Gatling Specialist Assistant. "
                    "Tugas Anda menyampaikan laporan akhir pengujian setelah mesin Gatling selesai mengeksekusi pengujian secara penuh dan nyata. "
                    "Sampaikan kepada pengguna secara ramah, profesional, dan jelas dalam Bahasa Indonesia bahwa proses pengujian telah tuntas "
                    "dieksekusi 100% oleh mesin Gatling selama durasi penuh. Sajikan rincian metrik performa (throughput, P95, P99, error rate) "
                    "dan tautan laporan resmi Gatling HTML dengan rapi menggunakan markdown."
                ),
            },
            {
                "role": "user",
                "content": f"Pesan Pengguna: '{user_msg}'\nHasil Eksekusi Tool (Telah tuntas dieksekusi selama durasi penuh): {tool_outputs[0]}",
            },
        ]
        synth_resp, _ = query_llm(model_mode, synthesis_messages)
        final_text = (
            synth_resp.get("content")
            if (synth_resp and synth_resp.get("content"))
            else ("\n\n".join(tool_outputs))
        )
        save_gatling_chat_message(db, user_id, "ai", final_text)
        return GatlingChatResponse(response=final_text, model_used=model_label)

    direct = ai_resp.get("content", "")
    if direct:
        save_gatling_chat_message(db, user_id, "ai", direct)
        return GatlingChatResponse(response=direct, model_used=model_label)

    fallback = "Maaf, saya tidak dapat memahami permintaan pengujian Gatling Anda."
    save_gatling_chat_message(db, user_id, "ai", fallback)
    return GatlingChatResponse(response=fallback, model_used=model_label)
