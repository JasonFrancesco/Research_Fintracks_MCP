"""
Publisher RabbitMQ untuk job stress test Gatling.

Dipakai MCP tool (enqueue_gatling_test) untuk MENITIPKAN job ke antrian, bukan
menjalankan Gatling langsung. Worker terpisah yang akan mengambil & mengeksekusi.
Inilah lapisan yang membuat alur jadi asinkron sungguhan:
    MCP tool -> publish ke RabbitMQ -> (worker consume)
"""
import os
import json
from typing import Dict, Any

try:
    import pika
except ModuleNotFoundError as e:
    # Pesan actionable: akar masalah paling umum adalah MCP server dijalankan
    # dengan Python global, bukan venv yang punya pika.
    raise ModuleNotFoundError(
        "Modul 'pika' tidak ditemukan. MCP server kemungkinan dijalankan dengan "
        "Python global. Jalankan ulang MCP server memakai venv: "
        "backend\\venv\\Scripts\\python.exe server.py"
    ) from e


def _conn_params() -> "pika.ConnectionParameters":
    host = os.getenv("RABBITMQ_HOST", "localhost")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))
    user = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")
    creds = pika.PlainCredentials(user, password)
    # heartbeat & timeout wajar agar koneksi tidak menggantung bila broker lambat
    return pika.ConnectionParameters(
        host=host, port=port, credentials=creds,
        heartbeat=30, blocked_connection_timeout=15, socket_timeout=10,
    )


def queue_name() -> str:
    return os.getenv("RABBITMQ_QUEUE", "gatling_jobs")


def publish_job(job: Dict[str, Any]) -> bool:
    """
    Kirim satu job ke antrian RabbitMQ. Mengembalikan True bila berhasil.

    Antrian dideklarasikan durable, dan pesan persistent, agar job tidak hilang
    bila broker restart sebelum worker sempat mengambilnya.
    """
    params = _conn_params()
    connection = pika.BlockingConnection(params)
    try:
        channel = connection.channel()
        q = queue_name()
        channel.queue_declare(queue=q, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=q,
            body=json.dumps(job).encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
                content_type="application/json",
            ),
        )
        return True
    finally:
        connection.close()
