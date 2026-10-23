"""
=============================================================================
 FIGURE TOOLS MODULE — figure_tools.py
=============================================================================
Logika MCP tool `search_figures`: validasi masukan, keyword match,
filter AND, sort deterministik, limit, dan format output JSON string.

Katalog HANYA diakses lewat load_catalog() dari Catalog_Adapter
(figure_catalog.py). Modul ini tidak pernah membaca file seed sendiri.
=============================================================================
"""
import json
from typing import Optional

from tools.figure_catalog import load_catalog, CatalogError

# Field wajib yang selalu disertakan pada tiap hasil (plus 'id').
_RESULT_FIELDS = (
    "id",
    "nama",
    "karakter",
    "brand",
    "skala",
    "tinggi_cm",
    "harga",
    "stok",
    "image_url",
    "shopee_url",
)


def _error(message: str) -> str:
    return json.dumps(
        {"count": 0, "results": [], "error": message}, ensure_ascii=False
    )


def _message(message: str) -> str:
    return json.dumps(
        {"count": 0, "results": [], "message": message}, ensure_ascii=False
    )


def _relevance(record: dict, q: str) -> int:
    """Skor relevansi deterministik untuk keyword match.

    - 2: cocok pada karakter atau nama diawali query.
    - 1: substring biasa pada nama.
    - 0: query kosong (semua kandidat setara).
    """
    if not q:
        return 0
    nama = str(record.get("nama", "")).lower()
    karakter = str(record.get("karakter", "")).lower()
    if q in karakter or nama.startswith(q):
        return 2
    return 1


def _matches_keyword(record: dict, q: str) -> bool:
    if not q:
        return True
    nama = str(record.get("nama", "")).lower()
    karakter = str(record.get("karakter", "")).lower()
    return q in nama or q in karakter


def search_figures_tool(
    query: str = "",
    max_price: Optional[float] = None,
    min_height: Optional[float] = None,
    max_height: Optional[float] = None,
    brand: Optional[str] = None,
    limit: int = 5,
) -> str:
    """
    Cari data produk figure One Piece dari katalog seed lokal.

    Alur: validasi -> load katalog -> keyword match -> filter AND -> sort ->
    limit -> format JSON string {count, results}. Lihat design.md Spec 2.
    """
    # (1) Validasi sebelum load — gagal cepat tanpa menjalankan pencarian.
    if max_price is not None and max_price < 0:
        return _error("max_price tidak boleh negatif.")
    if min_height is not None and min_height < 0:
        return _error("min_height tidak boleh negatif.")
    if max_height is not None and max_height < 0:
        return _error("max_height tidak boleh negatif.")
    if (
        min_height is not None
        and max_height is not None
        and min_height > max_height
    ):
        return _error("min_height tidak boleh lebih besar dari max_height.")
    if limit <= 0:
        return _error("limit harus lebih besar dari 0.")

    # (2) Load katalog lewat adapter; tangani kegagalan agar server tidak crash.
    try:
        records = load_catalog()
    except CatalogError as e:
        return _error(f"Katalog figure tidak tersedia: {e}")
    except Exception as e:  # noqa: BLE001 - jaga agar MCP server tidak crash
        return _error(f"Gagal membaca katalog: {e}")

    # (3) Katalog kosong (berbeda dari gagal baca).
    if records == []:
        return _message("Katalog figure kosong.")

    # (4) Keyword match + skor relevansi.
    q = query.strip().lower()
    candidates = []
    for record in records:
        if not _matches_keyword(record, q):
            continue
        candidates.append((record, _relevance(record, q)))

    # (5) Filter AND; filter None dilewati.
    brand_param = brand.strip().lower() if brand else None
    filtered = []
    for record, score in candidates:
        if max_price is not None and record.get("harga", 0) > max_price:
            continue
        if min_height is not None and record.get("tinggi_cm", 0) < min_height:
            continue
        if max_height is not None and record.get("tinggi_cm", 0) > max_height:
            continue
        if brand_param is not None and str(record.get("brand", "")).lower() != brand_param:
            continue
        filtered.append((record, score))

    # (6) Sort deterministik: skor menurun, harga menaik, id menaik.
    filtered.sort(
        key=lambda item: (
            -item[1],
            item[0].get("harga", 0),
            str(item[0].get("id", "")),
        )
    )

    # (7) Tidak ada hasil setelah filter.
    if not filtered:
        return _message("Tidak ada figure yang cocok dengan kriteria.")

    # (8) Limit.
    limited = filtered[:limit]

    # (9) Format output; tiap hasil memuat semua field wajib + id.
    results = []
    for record, _score in limited:
        results.append({field: record.get(field) for field in _RESULT_FIELDS})

    payload = {"count": len(results), "results": results}
    return json.dumps(payload, ensure_ascii=False)
