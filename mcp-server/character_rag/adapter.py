"""
=============================================================================
 CHARACTER ADAPTER — adapter.py
=============================================================================
Lapisan abstraksi yang membaca Character_CSV (pengetahuan karakter One Piece)
dan menyajikannya sebagai list[dict] seragam ke fase ingestion.

PENTING:
- Modul ini adalah SATU-SATUNYA titik yang membaca CSV secara langsung.
  Tanda tangan ``load_characters() -> list[dict]`` dikunci sebagai titik tukar
  sumber data: mengganti CSV dengan API/katalog lain cukup mengubah isi fungsi
  ini selama bentuk keluaran (dict berisi FIELDS) tetap sama, sehingga
  ingest.py dan konsumen lain tidak perlu ikut berubah.
- Modul ini TIDAK mengimpor llama-index, jadi bisa diuji mandiri sebelum
  dependency berat terpasang.
=============================================================================
"""
import csv
from pathlib import Path


class CharacterAdapterError(Exception):
    """Sumber data karakter tidak tersedia / tak terbaca."""


CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "one-piece-characters.csv"

FIELDS = (
    "ID",
    "Nama",
    "Julukan",
    "Afiliasi",
    "Peran",
    "Bounty (Beli)",
    "Buah Iblis",
    "Tipe Buah Iblis",
)


def load_characters() -> list[dict]:
    """
    Baca Character_CSV dan kembalikan satu record dict per baris karakter.

    Kontrak (STABIL — titik tukar sumber data):
    - Sukses          -> list[dict]; tiap dict memuat seluruh FIELDS apa adanya
                         (string, sudah di-strip).
    - File tidak ada  -> raise CharacterAdapterError (pesan menyebut path).
    - Gagal baca/parse-> raise CharacterAdapterError.
    """
    if not CSV_PATH.exists():
        raise CharacterAdapterError(
            f"Sumber data karakter tidak tersedia: {CSV_PATH} tidak ditemukan."
        )
    try:
        with open(CSV_PATH, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            records = [
                {k: (row.get(k) or "").strip() for k in FIELDS} for row in reader
            ]
    except OSError as e:
        raise CharacterAdapterError(f"Sumber data karakter tidak dapat dibaca: {e}.")
    return records
