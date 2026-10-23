"""
=============================================================================
 CATALOG ADAPTER — figure_catalog.py
=============================================================================
Lapisan abstraksi yang membaca katalog produk figure One Piece dan
menyajikannya ke Figure_Tools_Module dalam bentuk list[dict] yang seragam.

PENTING:
- Modul ini adalah SATU-SATUNYA titik yang perlu diubah ketika sumber data
  berpindah dari seed JSON lokal ke Shopee API. Cukup ganti isi load_catalog()
  agar memanggil Shopee API dan memetakan respons ke bentuk Figure_Record yang
  sama (field identik). Tanda tangan fungsi, bentuk keluaran, dan CatalogError
  tidak boleh berubah, sehingga figure_tools.py, server.py, dan konsumen lain
  tidak perlu ikut berubah.
- Sumber data SAAT INI adalah data PLACEHOLDER berupa seed JSON lokal
  (data/figures_seed.json). Data ini untuk keperluan demo dan akan digantikan
  oleh Shopee API di kemudian hari.

Modul ini TIDAK menyentuh database dan TIDAK butuh config/backend.
=============================================================================
"""
import json
from pathlib import Path


class CatalogError(Exception):
    """Katalog tidak tersedia / tak terbaca. Dilempar adapter, ditangkap figure_tools."""


REQUIRED_FIELDS = (
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

# Path seed dihitung relatif ke lokasi modul (tools/ -> parent mcp-server/ -> data/).
SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "figures_seed.json"


def load_catalog() -> list[dict]:
    """
    Baca seed katalog figure dan kembalikan list Figure_Record seragam.

    Kontrak:
    - Sukses             -> list[dict]; tiap dict memuat 'id' + seluruh REQUIRED_FIELDS,
                            dengan harga/stok dinormalkan ke int dan tinggi_cm ke float.
    - Katalog kosong     -> [] (BUKAN error; dibedakan dari gagal baca).
    - File tidak ada     -> raise CatalogError (pesan menyebut path).
    - JSON rusak         -> raise CatalogError.
    - Root bukan list    -> raise CatalogError.
    """
    if not SEED_PATH.exists():
        raise CatalogError(f"Katalog figure tidak ditemukan di {SEED_PATH}.")

    try:
        with open(SEED_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise CatalogError(f"Katalog figure tidak dapat dibaca: {e}.")
    except OSError as e:
        raise CatalogError(f"Katalog figure tidak dapat dibaca: {e}.")

    if not isinstance(data, list):
        raise CatalogError("Format katalog figure tidak valid (harus array).")

    if not data:
        return []

    records: list[dict] = []
    for index, entry in enumerate(data):
        record = dict(entry)
        if not record.get("id"):
            record["id"] = f"figure-{index + 1:03d}"
        try:
            record["harga"] = int(record["harga"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            record["stok"] = int(record["stok"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            record["tinggi_cm"] = float(record["tinggi_cm"])
        except (KeyError, TypeError, ValueError):
            pass
        records.append(record)

    return records
