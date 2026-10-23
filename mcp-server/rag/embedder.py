"""
Ollama embedder untuk fondasi RAG figure One Piece.

Komponen ini memanggil endpoint embeddings Ollama lokal di
``http://localhost:11434`` dengan model ``nomic-embed-text`` untuk mengubah teks
menjadi vektor embedding. Memakai ``urllib.request`` dari pustaka standar supaya
tidak menambah dependency HTTP baru.

Dipakai baik oleh Ingestion_Process (offline) maupun Retrieval_Process (runtime)
dengan model yang sama, sehingga embedding query dan embedding chunk konsisten.
"""
import json
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768


class EmbedderError(Exception):
    """Kesalahan yang dapat dijelaskan ke pengguna saat proses embedding gagal."""


def _post_json(path: str, payload: dict) -> dict:
    """
    Kirim satu POST JSON ke Ollama dan kembalikan body terurai.

    Memetakan kegagalan jaringan / HTTP ke EmbedderError dengan pesan jelas.
    Mengembalikan tuple-like via exception; sukses mengembalikan dict respons.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        # Baca body error untuk mendeteksi "model belum di-pull".
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        low = err_body.lower()
        if e.code == 404 or "not found" in low or "try pulling" in low:
            raise EmbedderError(
                f"Model '{EMBED_MODEL}' belum tersedia. "
                f"Jalankan: ollama pull {EMBED_MODEL}"
            ) from e
        # HTTPError lain (mis. 400) dilempar kembali untuk ditangani pemanggil
        # sebagai sinyal bahwa endpoint ini tidak cocok (dipakai untuk fallback).
        raise
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise EmbedderError(
            f"Ollama tidak dapat dihubungi di {OLLAMA_URL}. "
            f"Pastikan Ollama berjalan."
        ) from e

    try:
        return json.loads(body)
    except (ValueError, TypeError) as e:
        raise EmbedderError("Respons embedding Ollama tidak valid.") from e


def _extract_embedding(resp: dict):
    """
    Normalkan respons Ollama menjadi satu ``list[float]``.

    Mendukung dua bentuk respons:
    - ``/api/embeddings`` (versi lama): ``{"embedding": [...]}``
    - ``/api/embed`` (versi baru): ``{"embeddings": [[...]]}``
    """
    if not isinstance(resp, dict):
        return None
    if isinstance(resp.get("embedding"), list):
        return resp["embedding"]
    embeddings = resp.get("embeddings")
    if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
        return embeddings[0]
    return None


def embed_text(text: str) -> list[float]:
    """
    Meng-embed satu teks menjadi vektor float berdimensi ``EMBED_DIM``.

    Mencoba endpoint ``/api/embeddings`` (bentuk klasik) lebih dulu lalu fallback
    ke ``/api/embed`` (bentuk baru) agar kompatibel dengan beragam versi Ollama.
    Melempar ``EmbedderError`` dengan pesan jelas bila teks kosong, Ollama mati,
    model belum di-pull, respons tak valid, atau dimensi tidak sesuai.
    """
    if not isinstance(text, str) or not text.strip():
        raise EmbedderError("Teks untuk embedding kosong.")

    clean = text.strip()

    # Jalur utama: /api/embeddings dengan field prompt.
    try:
        resp = _post_json("/api/embeddings", {"model": EMBED_MODEL, "prompt": clean})
        embedding = _extract_embedding(resp)
    except urllib.error.HTTPError:
        embedding = None
    except EmbedderError:
        # URLError / model-not-found sudah dipetakan; coba fallback hanya untuk
        # kasus HTTP generik yang tidak dipetakan ke EmbedderError. Di sini
        # EmbedderError berarti kegagalan yang bermakna, jadi langsung dilempar.
        raise

    # Fallback: /api/embed dengan field input (Ollama versi baru).
    if embedding is None:
        try:
            resp = _post_json("/api/embed", {"model": EMBED_MODEL, "input": clean})
            embedding = _extract_embedding(resp)
        except urllib.error.HTTPError as e:
            raise EmbedderError("Respons embedding Ollama tidak valid.") from e

    if not embedding:
        raise EmbedderError("Respons embedding Ollama tidak valid.")

    if len(embedding) != EMBED_DIM:
        raise EmbedderError(
            f"Dimensi embedding dari '{EMBED_MODEL}' adalah {len(embedding)}, "
            f"berbeda dari EMBED_DIM={EMBED_DIM}. Sesuaikan EMBED_DIM dan "
            f"dimensi kolom vector pada DDL agar cocok."
        )

    return [float(v) for v in embedding]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Meng-embed daftar teks menjadi daftar vektor, satu per item masukan.

    Memanggil ``embed_text`` per item; bila salah satu gagal, ``EmbedderError``
    dipropagasikan ke pemanggil tanpa menghasilkan embedding tak valid.
    """
    return [embed_text(t) for t in texts]
