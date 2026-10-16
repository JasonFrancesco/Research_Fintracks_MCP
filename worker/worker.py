"""
Worker Service (Python) — konsumen antrian RabbitMQ untuk job stress test Gatling.

Peran dalam rantai:
    MCP tool (enqueue) -> RabbitMQ (gatling_jobs) -> [WORKER INI] -> Gatling nyata -> DB

Worker hidup terus-menerus, menunggu job. Saat job masuk, ia menjalankan Gatling
sungguhan lewat gatling_tools.run_queued_job (yang memakai gatling_runner Tahap 2),
lalu menyimpan metrik asli ke database.

Jalankan dengan:
    backend\\venv\\Scripts\\python.exe worker\\worker.py
"""
import os
import sys
import json
import time
from pathlib import Path

# Path setup: worker perlu akses modul mcp-server (tools) dan backend (config, models)
ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = ROOT / "mcp-server"
BACKEND_DIR = ROOT / "backend"
for p in (str(MCP_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Muat .env backend agar DATABASE_URL & RABBITMQ_* terbaca
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except Exception:
    pass

import pika
from tools.gatling_tools import run_queued_job


def _conn_params() -> pika.ConnectionParameters:
    host = os.getenv("RABBITMQ_HOST", "localhost")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))
    user = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")
    creds = pika.PlainCredentials(user, password)
    return pika.ConnectionParameters(
        host=host, port=port, credentials=creds, heartbeat=600,
        blocked_connection_timeout=300,
    )


def _on_message(channel, method, properties, body):
    """Dipanggil tiap satu job diterima dari antrian."""
    try:
        job = json.loads(body.decode("utf-8"))
    except Exception as e:
        print(f"[Worker] Pesan tidak valid, dibuang: {e}")
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    job_id = job.get("job_id", "?")
    print(f"\n[Worker] === Job #{job_id} diterima: {job.get('simulation_name')} -> {job.get('target_queue')} ===")
    print(f"[Worker] {job.get('virtual_users')} VUs selama {job.get('duration_seconds')}s. Menjalankan Gatling nyata...")

    t0 = time.time()
    result = run_queued_job(job)
    elapsed = round(time.time() - t0, 1)

    if result.get("ok"):
        print(f"[Worker] Job #{job_id} SELESAI dalam {elapsed}s | "
              f"Total: {result.get('total')} (OK={result.get('ok_req')}, KO={result.get('ko_req')}), "
              f"p95={result.get('p95')}ms")
    else:
        print(f"[Worker] Job #{job_id} GAGAL: {result.get('error')}")

    # Ack SETELAH selesai memproses (manual ack), sehingga bila worker mati di
    # tengah eksekusi, job akan dikirim ulang oleh broker, bukan hilang.
    channel.basic_ack(delivery_tag=method.delivery_tag)


def main():
    queue = os.getenv("RABBITMQ_QUEUE", "gatling_jobs")
    print("=" * 60)
    print("  FinTracks Gatling Worker (Python)")
    print(f"  Antrian : {queue}")
    print(f"  Broker  : {os.getenv('RABBITMQ_HOST','localhost')}:{os.getenv('RABBITMQ_PORT','5672')}")
    print("=" * 60)

    while True:
        try:
            connection = pika.BlockingConnection(_conn_params())
            channel = connection.channel()
            channel.queue_declare(queue=queue, durable=True)
            # Satu job sekaligus per worker (stress test berat, jangan paralel).
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue, on_message_callback=_on_message, auto_ack=False)
            print("[Worker] Siap. Menunggu job... (Ctrl+C untuk berhenti)")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[Worker] Koneksi RabbitMQ gagal: {e}. Coba lagi dalam 5 detik...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[Worker] Dihentikan oleh pengguna.")
            try:
                connection.close()
            except Exception:
                pass
            break
        except Exception as e:
            print(f"[Worker] Error tak terduga: {e}. Reconnect dalam 5 detik...")
            time.sleep(5)


if __name__ == "__main__":
    main()
