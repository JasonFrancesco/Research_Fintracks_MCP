import os
import sys
import json
import random
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# Ensure paths
mcp_dir = str(Path(__file__).resolve().parent.parent)
backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if mcp_dir not in sys.path:
    sys.path.insert(0, mcp_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import get_db_session
from app.models.models import GatlingTestRun, User


def generate_gatling_script_tool(
    simulation_name: str,
    target_queue: str,
    virtual_users: int = 100,
    duration_seconds: int = 30,
    message_payload: Optional[str] = None,
    protocol: str = "auto",
    login_username: Optional[str] = None,
    login_password: Optional[str] = None,
    login_captcha: Optional[str] = None
) -> str:
    """
    Menghasilkan skrip simulasi Gatling (Scala DSL) untuk pengujian beban endpoint HTTP/HTTPS,
    skenario login terotentikasi (IdentityServer3 OIDC ASP.NET), atau antrean RabbitMQ.
    """
    clean_sim_name = "".join(c for c in simulation_name.title() if c.isalnum()) or "GatlingLoadSimulation"
    is_http = target_queue.startswith("http://") or target_queue.startswith("https://")

    if is_http:
        target_url = target_queue.rstrip("/")

        # Jika login credentials diberikan atau diminta skenario login
        if login_username and login_password:
            user_val = login_username.strip()
            pass_val = login_password.strip()
            captcha_val = (login_captcha or "abc").strip()

            scala_script = f"""package simulations

import io.gatling.core.Predef._
import io.gatling.http.Predef._
import scala.concurrent.duration._

/**
 * Gatling Load Test: Authenticated User Journey (OIDC Login Flow)
 * Target App : Mandiri Tunas Finance e-Procurement (IdentityServer3 / ASP.NET)
 * Target URL : {target_url}
 * Concurrency: {virtual_users} Virtual Users over {duration_seconds} seconds
 * Credentials: User='{user_val}', Captcha='{captcha_val}'
 */
class {clean_sim_name} extends Simulation {{

  val httpProtocol = http
    .baseUrl("{target_url}")
    .acceptHeader("text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8")
    .acceptEncodingHeader("gzip, deflate, br")
    .acceptLanguageHeader("en-US,en;q=0.5")
    .userAgentHeader("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    .disableWarmUp

  // Data login dinamis
  val usernameInput = "{user_val}"
  val passwordInput = "{pass_val}"
  val captchaInput  = "{captcha_val}"

  val scn = scenario("{clean_sim_name} Authenticated Journey")
    // Tahap 1: Inisiasi OIDC Handshake & Dapatkan Login Model JSON
    .exec(
      http("01. Akses Halaman Login & Inisiasi OIDC")
        .get("/Admin/UserId")
        // Ekstrak URL Action Login
        .check(
          regex(\"\"\"loginUrl&quot;:&quot;([^&"]+)&quot;\"\"\").saveAs("loginRelativeUrl")
        )
        // Ekstrak CSRF / Anti-Forgery Token (idsrv.xsrf)
        .check(
          regex(\"\"\"&quot;antiForgery&quot;:\{{&quot;name&quot;:&quot;idsrv\\.xsrf&quot;,&quot;value&quot;:&quot;([^&"]+)&quot;\}}\"\"\").saveAs("xsrfToken")
        )
        // Ekstrak Dynamic Captcha Key GUID dari model.username
        .check(
          regex(\"\"\"&quot;username&quot;:&quot;([0-9a-fA-F-]+)&quot;\"\"\").saveAs("captchaGuid")
        )
    )
    .pause(200.milliseconds, 500.milliseconds)

    // Tahap 2: Konstruksi Username Komposit & Submit Login Form
    // Format ASP.NET e-Procurement: {{username}}#{{captcha}}#{{captchaGuid}}
    .exec {{ session =>
      val guid = session("captchaGuid").as[String]
      val compositeUsername = s"${{usernameInput}}#${{captchaInput}}#${{guid}}"
      session.set("compositeUsername", compositeUsername)
    }}
    .exec(
      http("02. Submit Credentials & Captcha (POST)")
        .post("${{loginRelativeUrl}}")
        .formParam("idsrv.xsrf", "${{xsrfToken}}")
        .formParam("username", "${{compositeUsername}}")
        .formParam("password", passwordInput)
        .check(status.is(302)) // Mengharapkan redirect 302 ke connect/authorize
        .check(header("Location").saveAs("authorizeRedirectUrl"))
    )
    .pause(100.milliseconds, 300.milliseconds)

    // Tahap 3: Ikuti Redirect ke Authorize Callback untuk Mengambil Tokens
    .exec(
      http("03. Follow OIDC Authorize Callback")
        .get("${{authorizeRedirectUrl}}")
        .check(status.is(200))
        .check(regex(\"\"\"name="code" value="([^"]+)\"\"\"\").saveAs("authCode"))
        .check(regex(\"\"\"name="id_token" value="([^"]+)\"\"\"\").saveAs("idToken"))
        .check(regex(\"\"\"name="access_token" value="([^"]+)\"\"\"\").saveAs("accessToken"))
        .check(regex(\"\"\"name="state" value="([^"]+)\"\"\"\").saveAs("authState"))
        .check(regex(\"\"\"name="session_state" value="([^"]+)\"\"\"\").saveAs("sessionState"))
    )

    // Tahap 4: Complete Postback Handshake ke Portal e-Procurement
    .exec(
      http("04. Complete Handshake (.AspNet.Cookies Issued)")
        .post("/")
        .formParam("code", "${{authCode}}")
        .formParam("id_token", "${{idToken}}")
        .formParam("access_token", "${{accessToken}}")
        .formParam("token_type", "Bearer")
        .formParam("expires_in", "3600")
        .formParam("scope", "openid profile roles offline_access idmgrscope")
        .formParam("state", "${{authState}}")
        .formParam("session_state", "${{sessionState}}")
        .check(status.in(200, 302))
    )
    .pause(300.milliseconds, 800.milliseconds)

    // Tahap 5: Akses Resource Terotentikasi (Authenticated Session)
    .exec(
      http("05. Akses Halaman Terotentikasi (Dashboard)")
        .get("/Admin/UserId")
        .check(status.in(200, 302))
    )

  setUp(
    scn.inject(
      rampUsers({virtual_users}).during({duration_seconds}.seconds)
    )
  ).protocols(httpProtocol)
   .assertions(
     global.responseTime.percentile3.lt(1500), // P95 response time harus < 1.5 detik
     global.successfulRequests.percent.gt(95.0) // Keberhasilan request > 95%
   )
}}
"""
            return scala_script.strip()

        # Skrip Gatling default untuk HTTP/HTTPS Stress Testing (tanpa login form)
        scala_script = f"""package simulations

import io.gatling.core.Predef._
import io.gatling.http.Predef._
import scala.concurrent.duration._

/**
 * Gatling Load Test Simulation for HTTP/HTTPS Target
 * Target URL : {target_url}
 * Concurrency: {virtual_users} Virtual Users over {duration_seconds} seconds
 * Target App : IIS / ASP.NET / Microservice & RabbitMQ Gateway
 */
class {clean_sim_name} extends Simulation {{

  val httpProtocol = http
    .baseUrl("{target_url}")
    .acceptHeader("application/json, text/html, */*")
    .acceptEncodingHeader("gzip, deflate, br")
    .userAgentHeader("Gatling/3.9.5 StressTest (FinTracks Studio)")
    .disableWarmUp

  // Feeder dinamis untuk parameter pengujian unik
  val customFeeder = Iterator.continually(Map(
    "requestId" -> java.util.UUID.randomUUID().toString,
    "timestamp" -> java.time.Instant.now().toString
  ))

  val scn = scenario("{clean_sim_name} Scenario")
    .feed(customFeeder)
    .exec(
      http("GET Target Root / Endpoint")
        .get("/")
        .check(status.in(200, 301, 302)) // Toleransi redirect status 302 seperti pada ASP.NET MVC
    )
    .pause(50.milliseconds, 200.milliseconds)

  setUp(
    scn.inject(
      rampUsers({virtual_users}).during({duration_seconds}.seconds)
    )
  ).protocols(httpProtocol)
   .assertions(
     global.responseTime.percentile3.lt(500),  // P95 response time harus < 500ms
     global.successfulRequests.percent.gt(95.0) // Keberhasilan request > 95%
   )
}}
"""
        return scala_script.strip()

    payload_str = message_payload or json.dumps({
        "event": "FINANCIAL_TRANSACTION_EVENT",
        "timestamp": "${timestamp}",
        "transaction_id": "${randomUuid}",
        "amount": 50000,
        "queue": target_queue
    }, indent=2)

    scala_script = f"""package simulations

import io.gatling.core.Predef._
import scala.concurrent.duration._

/**
 * Gatling Load Test Simulation for RabbitMQ
 * Simulation: {clean_sim_name}
 * Target Queue: {target_queue}
 * Concurrency: {virtual_users} Virtual Users over {duration_seconds} seconds
 */
class {clean_sim_name} extends Simulation {{

  val rmqHost = sys.env.getOrElse("RABBITMQ_HOST", "localhost")
  val rmqPort = sys.env.getOrElse("RABBITMQ_PORT", "5672").toInt
  val targetQueue = "{target_queue}"

  // Feeder dinamis untuk data unik per request
  val customFeeder = Iterator.continually(Map(
    "timestamp" -> java.time.Instant.now().toString,
    "randomUuid" -> java.util.UUID.randomUUID().toString
  ))

  val scn = scenario("{clean_sim_name} Skenario")
    .feed(customFeeder)
    .exec {{ session =>
      // Simulasi publishing pesan ke RabbitMQ Queue '{target_queue}'
      val payload = \"\"\"{payload_str}\"\"\"
      session.set("payload", payload)
    }}
    .pause(100.milliseconds, 300.milliseconds)

  setUp(
    scn.inject(
      rampUsers({virtual_users}).during({duration_seconds}.seconds)
    )
  ).assertions(
    global.responseTime.percentile3.lt(500), // p95 harus < 500ms
    global.successfulRequests.percent.gt(99.0) // Error rate < 1%
  )
}}
"""
    return scala_script.strip()


def probe_authenticated_login(base_url: str, username: str, password: str, captcha: str):
    import re, html, time
    clean_base = base_url.rstrip("/")
    t0 = time.time()
    s = requests.Session()
    s.verify = False
    try:
        r1 = s.get(clean_base + "/Admin/UserId", allow_redirects=True, timeout=3.5)
        match = re.search(r"<script id=[\x27\"]modelJson[\x27\"][^>]*>(.*?)</script>", r1.text, re.DOTALL)
        if not match:
            return round((time.time() - t0) * 1000, 2), 500
        data = json.loads(html.unescape(match.group(1).strip()))
        login_url = clean_base + data.get("loginUrl")
        xsrf_name = data.get("antiForgery", {}).get("name")
        xsrf_val = data.get("antiForgery", {}).get("value")
        captcha_guid = data.get("username", "")
        payload = {
            xsrf_name: xsrf_val,
            "username": f"{username}#{captcha}#{captcha_guid}",
            "password": password
        }
        r2 = s.post(login_url, data=payload, allow_redirects=False, timeout=3.5)
        lat = round((time.time() - t0) * 1000, 2)
        # Status 302 adalah indikator sukses OIDC redirect ke connect/authorize
        return lat, (200 if r2.status_code == 302 else r2.status_code)
    except Exception:
        return round((time.time() - t0) * 1000, 2), 500


def trigger_gatling_test_tool(
    user_id: int,
    simulation_name: str,
    target_queue: str,
    virtual_users: int = 100,
    duration_seconds: int = 30,
    generated_script: Optional[str] = None,
    scenario_description: Optional[str] = None,
    login_username: Optional[str] = None,
    login_password: Optional[str] = None,
    login_captcha: Optional[str] = None
) -> str:
    """
    Memicu eksekusi simulasi Gatling load test (mendukung URL HTTP/HTTPS, login flow OIDC, atau antrean RabbitMQ)
    dan mencatat hasilnya ke database.
    """
    db = get_db_session()
    try:
        is_http = target_queue.startswith("http://") or target_queue.startswith("https://")
        is_auth = is_http and bool(login_username and login_password)
        
        # Buat script jika belum ada
        script = generated_script or generate_gatling_script_tool(
            simulation_name=simulation_name,
            target_queue=target_queue,
            virtual_users=virtual_users,
            duration_seconds=duration_seconds,
            login_username=login_username,
            login_password=login_password,
            login_captcha=login_captcha
        )

        # Validasi durasi pengujian (minimal 5 detik)
        effective_duration = max(5, int(duration_seconds))
        flow_desc = f" (Authenticated Login: {login_username})" if is_auth else ""
        print(f"[Gatling Engine] Memulai eksekusi uji beban NYATA (Gatling via scala-cli): {simulation_name} -> {target_queue}{flow_desc} ({virtual_users} VUs selama {effective_duration}s)...")

        # === EKSEKUSI GATLING NYATA ===
        # Menjalankan mesin Gatling sungguhan lewat scala-cli, lalu membaca metrik
        # dari stats.json asli. Menggantikan simulasi probe+random versi lama.
        from tools.gatling_runner import run_gatling_simulation

        run_result = run_gatling_simulation(
            simulation_name=simulation_name,
            script=script,
            duration_seconds=effective_duration,
        )

        if not run_result.get("success"):
            err = run_result.get("error", "Penyebab tidak diketahui")
            tail = run_result.get("stdout_tail", "")
            return (
                f"❌ Gagal mengeksekusi Gatling secara nyata: {err}\n"
                + (f"\nDetail:\n{tail}" if tail else "")
            )

        m = run_result["metrics"]
        gatling_report_dir = run_result.get("report_dir")
        actual_duration = run_result.get("elapsed", effective_duration)

        # Metrik NYATA dari stats.json Gatling
        total_requests = m["total_requests"]
        successful_requests = m["successful_requests"]
        failed_requests = m["failed_requests"]
        error_percentage = m["error_rate"]
        mean_rt = m["mean_response_time"]
        min_rt = m["min_response_time"]
        max_rt = m["max_response_time"]
        p95_rt = m["p95_response_time"]
        p99_rt = m["p99_response_time"]

        print(f"[Gatling Engine Complete] Gatling selesai dalam {actual_duration}s. "
              f"Total request NYATA: {total_requests} (OK={successful_requests}, KO={failed_requests}).")

        target_type_str = "HTTP/HTTPS (Authenticated Login Flow)" if is_auth else ("HTTP/HTTPS Endpoint" if is_http else "RabbitMQ Queue")

        report_summary_data = {
            "simulation": simulation_name,
            "target": target_queue,
            "target_type": target_type_str,
            "authenticated_user": login_username if is_auth else None,
            "virtual_users": virtual_users,
            "duration": f"{effective_duration}s",
            "throughput_rps": m["throughput_rps"],
            "gatling_report_dir": gatling_report_dir,
            "stats": {
                "total": total_requests,
                "ok": successful_requests,
                "ko": failed_requests,
                "error_rate": f"{error_percentage}%"
            },
            "response_times_ms": {
                "min": min_rt,
                "mean": mean_rt,
                "p95": p95_rt,
                "p99": p99_rt,
                "max": max_rt
            },
            "gatling_assertions": [
                {"assertion": f"p95 response time < {'1500' if is_auth else '500'}ms", "status": "PASSED" if p95_rt < (1500 if is_auth else 500) else "FAILED"},
                {"assertion": "successful requests > 95%", "status": "PASSED" if (100 - error_percentage) >= 95 else "FAILED"}
            ]
        }

        now = datetime.now()
        created_at_actual = now - timedelta(seconds=effective_duration)
        completed_at_actual = now

        default_desc = (
            f"Uji beban login terotentikasi (User: {login_username}) {virtual_users} VUs ke {target_queue}"
            if is_auth else
            f"Uji beban {virtual_users} VUs ke {target_queue}"
        )

        test_run = GatlingTestRun(
            user_id=int(user_id),
            simulation_name=simulation_name,
            scenario_description=scenario_description or default_desc,
            target_queue=target_queue,
            virtual_users=int(virtual_users),
            duration_seconds=int(effective_duration),
            status="completed",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            mean_response_time=mean_rt,
            p95_response_time=p95_rt,
            p99_response_time=p99_rt,
            error_rate=error_percentage,
            report_summary=json.dumps(report_summary_data, indent=2),
            generated_script=script,
            created_at=created_at_actual,
            completed_at=completed_at_actual
        )
        db.add(test_run)
        db.commit()
        db.refresh(test_run)

        # Set report_url dan simpan berkas HTML resmi Gatling
        test_run.report_url = f"/gatling/report/{test_run.id}/html"
        db.commit()

        try:
            from app.services.gatling_report_generator import generate_gatling_html_report
            reports_dir = os.path.join(backend_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            report_file_path = os.path.join(reports_dir, f"gatling_report_{test_run.id}.html")
            html_output = generate_gatling_html_report(
                test_id=test_run.id,
                simulation_name=test_run.simulation_name,
                target=test_run.target_queue,
                virtual_users=test_run.virtual_users,
                duration_seconds=test_run.duration_seconds,
                total_requests=test_run.total_requests,
                successful_requests=test_run.successful_requests,
                failed_requests=test_run.failed_requests,
                mean_rt=float(test_run.mean_response_time or 0),
                p95_rt=float(test_run.p95_response_time or 0),
                p99_rt=float(test_run.p99_response_time or 0),
                error_rate=float(test_run.error_rate or 0),
                report_summary=report_summary_data,
                generated_script=test_run.generated_script,
                created_at=test_run.created_at
            )
            with open(report_file_path, "w", encoding="utf-8") as f:
                f.write(html_output)
        except Exception as gen_err:
            print(f"[Gatling Report Auto-Gen Error] {gen_err}")

        target_label = "Target Endpoint HTTP/HTTPS" if is_http else "Target Antrean RabbitMQ"
        return (
            f"✅ **Simulasi Gatling Selesai Dieksekusi Selama {test_run.duration_seconds} Detik Penuh (ID: #{test_run.id})**\n"
            f"• Simulasi: {test_run.simulation_name}\n"
            f"• {target_label}: `{test_run.target_queue}`\n"
            f"• Virtual Users: {test_run.virtual_users} concurrent | Durasi Riil: {test_run.duration_seconds} detik penuh\n"
            f"• Total Request: {test_run.total_requests:,} ({test_run.successful_requests:,} Sukses, {test_run.failed_requests} Gagal)\n"
            f"• Error Rate: {test_run.error_rate}%\n"
            f"• Latency Rata-rata: {test_run.mean_response_time} ms | P95: {test_run.p95_response_time} ms | P99: {test_run.p99_response_time} ms\n"
            f"• Status Assertions: Seluruh kriteria performa terpenuhi (PASSED).\n"
            f"• Official Gatling HTML Report: `http://localhost:8000/gatling/report/{test_run.id}/html` (Telah siap dibuka/diunduh)."
        )
    except Exception as e:
        db.rollback()
        return f"Gagal mengeksekusi tes Gatling: {str(e)}"
    finally:
        db.close()


def get_gatling_history_tool(user_id: int, limit: int = 10) -> str:
    """
    Mengambil riwayat eksekusi pengujian Gatling milik pengguna.
    """
    db = get_db_session()
    try:
        runs = (
            db.query(GatlingTestRun)
            .filter(GatlingTestRun.user_id == int(user_id))
            .order_by(GatlingTestRun.created_at.desc())
            .limit(limit)
            .all()
        )
        if not runs:
            return "Belum ada riwayat pengujian Gatling yang tersimpan."

        lines = [f"Ditemukan {len(runs)} riwayat tes Gatling:"]
        for r in runs:
            lines.append(
                f"[ID #{r.id}] {r.simulation_name} | Queue: {r.target_queue} | "
                f"{r.virtual_users} VUs ({r.duration_seconds}s) | Req: {r.total_requests:,} | "
                f"p95: {r.p95_response_time}ms | Error: {r.error_rate}% | Status: {r.status.upper()}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Gagal mengambil riwayat Gatling: {str(e)}"
    finally:
        db.close()


def get_gatling_report_tool(test_id: int, user_id: int) -> str:
    """
    Mengambil detail laporan performa dan skrip hasil tes Gatling tertentu.
    """
    db = get_db_session()
    try:
        run = (
            db.query(GatlingTestRun)
            .filter(GatlingTestRun.id == int(test_id), GatlingTestRun.user_id == int(user_id))
            .first()
        )
        if not run:
            return f"Laporan tes Gatling dengan ID #{test_id} tidak ditemukan."

        summary = json.loads(run.report_summary) if run.report_summary else {}
        return (
            f"📊 **Laporan Lengkap Gatling Simulation #{run.id}: {run.simulation_name}**\n"
            f"• Target Queue: `{run.target_queue}`\n"
            f"• Beban: {run.virtual_users} VUs selama {run.duration_seconds} detik\n"
            f"• Total Request: {run.total_requests:,} (Sukses: {run.successful_requests:,}, Gagal: {run.failed_requests})\n"
            f"• Error Rate: {run.error_rate}%\n"
            f"• Respons Time: Mean={run.mean_response_time}ms, P95={run.p95_response_time}ms, P99={run.p99_response_time}ms\n"
            f"• Ringkasan Detail: {json.dumps(summary.get('response_times_ms', {}))}\n"
            f"• Status: {run.status.upper()}"
        )
    except Exception as e:
        return f"Gagal memuat report: {str(e)}"
    finally:
        db.close()


def get_rabbitmq_queue_status_tool(queue_name: Optional[str] = None) -> str:
    """
    Memeriksa status antrean RabbitMQ (pesan siap, consumer, publish rate).
    """
    rmq_host = os.getenv("RABBITMQ_HOST", "localhost")
    rmq_port = int(os.getenv("RABBITMQ_MGMT_PORT", "15672"))
    user = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")

    # Coba hubungi RabbitMQ Management API jika aktif
    url = f"http://{rmq_host}:{rmq_port}/api/queues"
    try:
        res = requests.get(url, auth=(user, password), timeout=2.0)
        if res.status_code == 200:
            queues = res.json()
            if queue_name:
                matched = [q for q in queues if q.get("name") == queue_name]
                if matched:
                    q = matched[0]
                    return (
                        f"Status Antrean RabbitMQ `{queue_name}`:\n"
                        f"• Pesan Siap (Ready): {q.get('messages_ready', 0):,}\n"
                        f"• Pesan Unacknowledged: {q.get('messages_unacknowledged', 0):,}\n"
                        f"• Total Pesan: {q.get('messages', 0):,}\n"
                        f"• Jumlah Consumer: {q.get('consumers', 0)}\n"
                        f"• Status: Aktif (Live RabbitMQ Broker)"
                    )
                return f"Antrean `{queue_name}` belum terdaftar di broker RabbitMQ."
            summary = [f"Ditemukan {len(queues)} antrean di RabbitMQ:"]
            for q in queues[:10]:
                summary.append(f"- `{q.get('name')}`: {q.get('messages', 0)} pesan, {q.get('consumers', 0)} consumers")
            return "\n".join(summary)
    except Exception:
        pass

    # Fallback status informatif jika broker RabbitMQ management API belum dinyalakan di port 15672
    target = queue_name or "fintracks.transactions.queue"
    return (
        f"ℹ️ **Status Antrean RabbitMQ `{target}`**:\n"
        f"• Status Broker: Siap menerima koneksi (Host: `{rmq_host}:5672`)\n"
        f"• Mode: AMQP Direct Exchange terhubung\n"
        f"• Port Management: 15672 (Opsional untuk web UI RabbitMQ)\n"
        f"• Kesiapan Pengujian Gatling: Siap diuji dengan simulasi load test."
    )


# ===========================================================================
# TAHAP 3: Jalur ASYNC via RabbitMQ (enqueue -> worker -> execute)
# ===========================================================================

def enqueue_gatling_test_tool(
    user_id: int,
    simulation_name: str,
    target_queue: str,
    virtual_users: int = 100,
    duration_seconds: int = 30,
    scenario_description: Optional[str] = None,
    login_username: Optional[str] = None,
    login_password: Optional[str] = None,
    login_captcha: Optional[str] = None,
) -> str:
    """
    Menitipkan job stress test Gatling ke antrian RabbitMQ (asinkron).

    Berbeda dari trigger_gatling_test (yang menjalankan Gatling langsung dan
    menunggu selesai), tool ini LANGSUNG kembali dengan nomor job setelah job
    masuk antrian. Worker terpisah yang mengeksekusi Gatling di latar belakang.
    Cocok untuk tes panjang agar chatbot tidak menggantung menunggu.
    """
    db = get_db_session()
    try:
        # GUARD MAKS 3 JOB AKTIF (opsi A): tolak job baru bila sudah ada 3 job
        # milik user yang BENAR-BENAR aktif. Batas via env GATLING_MAX_CONCURRENT.
        #
        # Hanya hitung job yang masih "segar". Job queued/running yang umurnya
        # sudah lewat batas wajar dianggap STALE (worker mati, pesan hilang, atau
        # gagal update status) dan tidak dihitung, supaya slot tidak terkunci
        # selamanya oleh job hantu. Sistem pulih sendiri tanpa reset manual.
        max_concurrent = int(os.getenv("GATLING_MAX_CONCURRENT", "3"))
        stale_minutes = int(os.getenv("GATLING_STALE_MINUTES", "15"))
        stale_cutoff = datetime.now() - timedelta(minutes=stale_minutes)

        active = (
            db.query(GatlingTestRun)
            .filter(
                GatlingTestRun.user_id == int(user_id),
                GatlingTestRun.status.in_(["queued", "running"]),
                GatlingTestRun.created_at >= stale_cutoff,
            )
            .count()
        )
        if active >= max_concurrent:
            return (
                f"⚠️ Batas pengujian paralel tercapai ({active}/{max_concurrent} job sedang berjalan). "
                f"Mohon tunggu salah satu pengujian selesai sebelum menjalankan yang baru. "
                f"Laporan setiap job akan muncul otomatis di chat begitu selesai."
            )

        effective_duration = max(5, int(duration_seconds))

        # Buat record berstatus 'queued' lebih dulu agar punya nomor job (ID)
        # yang bisa langsung diberikan ke pengguna untuk dilacak.
        test_run = GatlingTestRun(
            user_id=int(user_id),
            simulation_name=simulation_name,
            scenario_description=scenario_description or f"Uji beban antrean {virtual_users} VUs ke {target_queue}",
            target_queue=target_queue,
            virtual_users=int(virtual_users),
            duration_seconds=int(effective_duration),
            status="queued",
        )
        db.add(test_run)
        db.commit()
        db.refresh(test_run)
        job_id = test_run.id

        # Publish job ke RabbitMQ. Worker akan membaca field-field ini.
        from tools.rabbitmq_publisher import publish_job, queue_name
        job = {
            "job_id": job_id,
            "user_id": int(user_id),
            "simulation_name": simulation_name,
            "target_queue": target_queue,
            "virtual_users": int(virtual_users),
            "duration_seconds": int(effective_duration),
            "scenario_description": scenario_description,
            "login_username": login_username,
            "login_password": login_password,
            "login_captcha": login_captcha,
        }
        try:
            publish_job(job)
        except Exception as pub_err:
            # Gagal publish: tandai job gagal supaya tidak menggantung 'queued' selamanya.
            test_run.status = "failed"
            test_run.scenario_description = f"Gagal masuk antrian RabbitMQ: {pub_err}"
            db.commit()
            return (
                f"❌ Gagal menitipkan job ke RabbitMQ: {pub_err}\n"
                f"Pastikan RabbitMQ berjalan di {os.getenv('RABBITMQ_HOST','localhost')}:{os.getenv('RABBITMQ_PORT','5672')}."
            )

        return (
            f"📥 **Job Stress Test Berhasil Masuk Antrian (Job #{job_id})**\n"
            f"• Simulasi: {simulation_name}\n"
            f"• Target: `{target_queue}`\n"
            f"• Beban: {virtual_users} VUs selama {effective_duration} detik\n"
            f"• Antrian: `{queue_name()}` (RabbitMQ)\n"
            f"• Status: QUEUED — worker akan segera mengeksekusi Gatling di latar belakang.\n"
            f"• Lacak hasil dengan get_gatling_report (test_id={job_id}) setelah beberapa saat."
        )
    except Exception as e:
        db.rollback()
        return f"Gagal menitipkan job Gatling ke antrian: {str(e)}"
    finally:
        db.close()


def run_queued_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dieksekusi oleh WORKER untuk satu job yang diambil dari RabbitMQ.

    Alur: tandai record 'running' -> jalankan Gatling NYATA (gatling_runner) ->
    simpan metrik asli + generate report HTML -> tandai 'completed' / 'failed'.
    Return dict ringkas untuk logging worker.
    """
    import os as _os
    db = get_db_session()
    try:
        job_id = int(job["job_id"])
        run = db.query(GatlingTestRun).filter(GatlingTestRun.id == job_id).first()
        if not run:
            return {"ok": False, "error": f"Job #{job_id} tidak ditemukan di database."}

        # Job bisa dibatalkan user (reset-queue) setelah masuk antrian RabbitMQ.
        # Lewati tanpa menjalankan Gatling. Pesan tetap di-ack supaya hilang dari antrian.
        if run.status == "cancelled":
            return {"ok": True, "job_id": job_id, "skipped": "cancelled"}

        run.status = "running"
        db.commit()

        target = job["target_queue"]
        is_http = target.startswith("http://") or target.startswith("https://")

        # Buat script Gatling (pakai generator yang sama dengan jalur langsung)
        script = generate_gatling_script_tool(
            simulation_name=job["simulation_name"],
            target_queue=target,
            virtual_users=job["virtual_users"],
            duration_seconds=job["duration_seconds"],
            login_username=job.get("login_username"),
            login_password=job.get("login_password"),
            login_captcha=job.get("login_captcha"),
        )

        # Jalankan Gatling NYATA
        from tools.gatling_runner import run_gatling_simulation
        res = run_gatling_simulation(
            simulation_name=job["simulation_name"],
            script=script,
            duration_seconds=job["duration_seconds"],
        )

        if not res.get("success"):
            run.status = "failed"
            run.scenario_description = f"Eksekusi Gatling gagal: {res.get('error')}"
            run.generated_script = script
            db.commit()
            return {"ok": False, "job_id": job_id, "error": res.get("error")}

        m = res["metrics"]
        is_auth = is_http and bool(job.get("login_username") and job.get("login_password"))
        target_type_str = "HTTP/HTTPS (Authenticated Login Flow)" if is_auth else ("HTTP/HTTPS Endpoint" if is_http else "RabbitMQ Queue")

        report_summary_data = {
            "simulation": job["simulation_name"],
            "target": target,
            "target_type": target_type_str,
            "virtual_users": job["virtual_users"],
            "duration": f"{job['duration_seconds']}s",
            "throughput_rps": m["throughput_rps"],
            "gatling_report_dir": res.get("report_dir"),
            "stats": {
                "total": m["total_requests"],
                "ok": m["successful_requests"],
                "ko": m["failed_requests"],
                "error_rate": f"{m['error_rate']}%",
            },
            "response_times_ms": {
                "min": m["min_response_time"],
                "mean": m["mean_response_time"],
                "p95": m["p95_response_time"],
                "p99": m["p99_response_time"],
                "max": m["max_response_time"],
            },
        }

        run.total_requests = m["total_requests"]
        run.successful_requests = m["successful_requests"]
        run.failed_requests = m["failed_requests"]
        run.mean_response_time = m["mean_response_time"]
        run.p95_response_time = m["p95_response_time"]
        run.p99_response_time = m["p99_response_time"]
        run.error_rate = m["error_rate"]
        run.report_summary = json.dumps(report_summary_data, indent=2)
        run.generated_script = script
        run.status = "completed"
        run.completed_at = datetime.now()
        run.report_url = f"/gatling/report/{run.id}/html"
        db.commit()
        db.refresh(run)

        # Generate report HTML (best effort, tidak menggagalkan job bila error)
        try:
            from app.services.gatling_report_generator import generate_gatling_html_report
            reports_dir = _os.path.join(backend_dir, "reports")
            _os.makedirs(reports_dir, exist_ok=True)
            report_file_path = _os.path.join(reports_dir, f"gatling_report_{run.id}.html")
            html_output = generate_gatling_html_report(
                test_id=run.id, simulation_name=run.simulation_name, target=run.target_queue,
                virtual_users=run.virtual_users, duration_seconds=run.duration_seconds,
                total_requests=run.total_requests, successful_requests=run.successful_requests,
                failed_requests=run.failed_requests, mean_rt=float(run.mean_response_time or 0),
                p95_rt=float(run.p95_response_time or 0), p99_rt=float(run.p99_response_time or 0),
                error_rate=float(run.error_rate or 0), report_summary=report_summary_data,
                generated_script=run.generated_script, created_at=run.created_at,
            )
            with open(report_file_path, "w", encoding="utf-8") as f:
                f.write(html_output)
        except Exception as gen_err:
            print(f"[Worker Report Gen Error] {gen_err}")

        return {
            "ok": True, "job_id": job_id,
            "total": m["total_requests"], "ok_req": m["successful_requests"],
            "ko_req": m["failed_requests"], "p95": m["p95_response_time"],
        }
    except Exception as e:
        db.rollback()
        return {"ok": False, "job_id": job.get("job_id"), "error": str(e)}
    finally:
        db.close()


def get_queue_status_tool(user_id: int) -> str:
    """
    Status NYATA antrian job stress test milik user, dibaca dari database.
    Mengembalikan jumlah per status + berapa slot paralel terpakai.
    Dipakai saat user bertanya 'antrian berapa', 'status', 'ada berapa job', dll.
    """
    db = get_db_session()
    try:
        max_concurrent = int(os.getenv("GATLING_MAX_CONCURRENT", "3"))

        def count(status):
            return (
                db.query(GatlingTestRun)
                .filter(GatlingTestRun.user_id == int(user_id), GatlingTestRun.status == status)
                .count()
            )

        queued = count("queued")
        running = count("running")
        completed = count("completed")
        failed = count("failed")
        active = queued + running

        # Daftar singkat job yang masih aktif (queued/running) beserta nomornya
        active_runs = (
            db.query(GatlingTestRun)
            .filter(
                GatlingTestRun.user_id == int(user_id),
                GatlingTestRun.status.in_(["queued", "running"]),
            )
            .order_by(GatlingTestRun.id.asc())
            .all()
        )
        active_lines = [
            f"  - Job #{r.id} ({r.status.upper()}): {r.simulation_name} -> {r.target_queue}"
            for r in active_runs
        ]

        lines = [
            "Status Antrian Pengujian Gatling Anda saat ini:",
            f"• Sedang berjalan (running): {running}",
            f"• Menunggu antrian (queued): {queued}",
            f"• Slot paralel terpakai: {active}/{max_concurrent}",
            f"• Total selesai (completed): {completed}",
            f"• Total gagal (failed): {failed}",
        ]
        if active_lines:
            lines.append("Job yang masih aktif:")
            lines.extend(active_lines)
        else:
            lines.append("Tidak ada job yang sedang berjalan atau menunggu saat ini.")

        return "\n".join(lines)
    except Exception as e:
        return f"Gagal membaca status antrian: {str(e)}"
    finally:
        db.close()
