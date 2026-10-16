"""
Migrasi manual satu kali: tambah kolom report_posted_to_chat ke gatling_test_runs.

Project ini memakai Base.metadata.create_all (bukan Alembic), yang TIDAK menambah
kolom baru ke tabel yang sudah ada. Jadi kolom ini harus ditambah manual untuk DB
yang sudah berisi tabel gatling_test_runs.

Aman dijalankan berulang: memakai IF NOT EXISTS (Postgres) dan pengecekan untuk SQLite.
Jalankan: backend\\venv\\Scripts\\python.exe backend\\migrate_add_report_posted.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.database import engine


def column_exists_sqlite(conn, table, column) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def main():
    dialect = engine.url.get_backend_name()
    table = "gatling_test_runs"
    column = "report_posted_to_chat"

    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} BOOLEAN DEFAULT FALSE"
            ))
            print(f"[Migrasi] Postgres: kolom {column} dipastikan ada di {table}.")
        elif dialect == "sqlite":
            if column_exists_sqlite(conn, table, column):
                print(f"[Migrasi] SQLite: kolom {column} sudah ada, dilewati.")
            else:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN {column} BOOLEAN DEFAULT 0"
                ))
                print(f"[Migrasi] SQLite: kolom {column} ditambahkan.")
        else:
            # Dialek lain: coba cara umum, biarkan error muncul bila tidak didukung
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} BOOLEAN DEFAULT FALSE"))
            print(f"[Migrasi] {dialect}: kolom {column} ditambahkan.")

    print("[Migrasi] Selesai.")


if __name__ == "__main__":
    main()
