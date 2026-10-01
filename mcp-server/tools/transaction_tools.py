import sys
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

# Add mcp-server and backend directories to sys.path
mcp_dir = str(Path(__file__).resolve().parent.parent)
backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if mcp_dir not in sys.path:
    sys.path.insert(0, mcp_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import get_db_session
from app.models.models import Transaction, User

def _parse_date(date_val) -> datetime:
    if isinstance(date_val, datetime):
        return date_val
    if not date_val:
        return datetime.now()
    date_str = str(date_val).split('T')[0]
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except Exception:
        return datetime.now()


def _parse_date_strict(date_val) -> Optional[datetime]:
    """
    Versi _parse_date yang mengembalikan None jika tanggal tidak valid.
    Wajib dipakai untuk PENCARIAN transaksi: mundur ke datetime.now() saat gagal
    parse akan membuat kita mencari di hari yang salah dan berpotensi mengubah
    transaksi yang keliru.
    """
    if isinstance(date_val, datetime):
        return date_val
    if date_val is None:
        return None
    date_str = str(date_val).strip().split('T')[0]
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _format_tx_line(t: Transaction) -> str:
    d_str = t.transaction_date.strftime('%Y-%m-%d') if hasattr(t.transaction_date, 'strftime') else str(t.transaction_date)[:10]
    return f"[{t.id}] {d_str} | {t.title} | {t.category} | {t.transaction_type}: Rp {float(t.amount):,.2f}"


def _find_by_criteria(
    db: Session,
    user_id: int,
    match_title: Optional[str] = None,
    match_date: Optional[str] = None,
) -> List[Transaction]:
    """
    Mencari transaksi milik user berdasarkan judul dan/atau tanggal.

    Pencocokan judul bertingkat, berhenti di tingkat pertama yang menghasilkan
    kandidat, supaya kata kunci spesifik tidak tertelan hasil yang lebih longgar:
      1. sama persis (abaikan besar kecil huruf)
      2. judul mengandung kata kunci sebagai substring
      3. seluruh kata pada kata kunci muncul di judul, urutan bebas
    """
    query = db.query(Transaction).filter(Transaction.user_id == int(user_id))

    parsed_date = _parse_date_strict(match_date)
    if parsed_date is not None:
        day_start = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
        # Rentang setengah terbuka, bukan cast ke DATE, agar tetap ramah index
        # dan tidak bergantung pada timezone sesi database.
        query = query.filter(
            Transaction.transaction_date >= day_start,
            Transaction.transaction_date < day_start + timedelta(days=1),
        )

    rows = query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).all()

    keyword = (match_title or "").strip().lower()
    if not keyword:
        return rows

    exact = [t for t in rows if (t.title or "").strip().lower() == keyword]
    if exact:
        return exact

    substring = [t for t in rows if keyword in (t.title or "").lower()]
    if substring:
        return substring

    tokens = [tok for tok in keyword.split() if tok]
    if not tokens:
        return []
    return [t for t in rows if all(tok in (t.title or "").lower() for tok in tokens)]


def _resolve_single_transaction(
    db: Session,
    user_id: int,
    transaction_id: Optional[int] = None,
    match_title: Optional[str] = None,
    match_date: Optional[str] = None,
) -> Tuple[Optional[Transaction], Optional[str]]:
    """
    Menentukan satu transaksi target. Return (transaksi, pesan_error).

    Ambiguitas TIDAK diselesaikan sendiri: bila kandidat lebih dari satu, kita
    kembalikan daftarnya dan meminta ID. Menebak kandidat pertama berarti
    mengubah data yang salah tanpa disadari pengguna.
    """
    if transaction_id is not None:
        try:
            tid = int(transaction_id)
        except (ValueError, TypeError):
            return None, f"ID transaksi '{transaction_id}' bukan angka yang valid."
        tx = db.query(Transaction).filter(
            Transaction.id == tid,
            Transaction.user_id == int(user_id),
        ).first()
        if not tx:
            return None, f"Transaksi dengan ID {tid} tidak ditemukan atau Anda tidak punya akses."
        return tx, None

    has_title = bool((match_title or "").strip())
    has_date = match_date is not None and str(match_date).strip() != ""

    if not has_title and not has_date:
        return None, (
            "Tidak bisa menentukan transaksi mana yang dimaksud. "
            "Sertakan salah satu: ID transaksi, judul transaksi (match_title), atau tanggal (match_date)."
        )

    if has_date and _parse_date_strict(match_date) is None:
        return None, f"Tanggal pencarian '{match_date}' tidak dikenali. Gunakan format YYYY-MM-DD."

    candidates = _find_by_criteria(db, user_id, match_title, match_date)

    criteria_desc = []
    if has_title:
        criteria_desc.append(f"judul mengandung '{str(match_title).strip()}'")
    if has_date:
        criteria_desc.append(f"tanggal {_parse_date_strict(match_date).strftime('%Y-%m-%d')}")
    criteria_str = " dan ".join(criteria_desc)

    if not candidates:
        return None, (
            f"Tidak ada transaksi dengan {criteria_str}. "
            f"Coba periksa daftar transaksi terlebih dahulu untuk memastikan judul atau tanggalnya."
        )

    if len(candidates) > 1:
        listing = "\n".join(_format_tx_line(t) for t in candidates[:10])
        extra = f"\n(dan {len(candidates) - 10} transaksi lain)" if len(candidates) > 10 else ""
        return None, (
            f"Ditemukan {len(candidates)} transaksi dengan {criteria_str}, jadi belum ada yang diubah. "
            f"Sebutkan ID transaksi yang dimaksud:\n{listing}{extra}"
        )

    return candidates[0], None

def create_transaction_tool(user_id: int, title: str, amount: float, category: str, transaction_type: str, date: str, note: Optional[str] = None):
    """
    Menambah transaksi baru ke dalam catatan keuangan.
    transaction_type harus berupa 'income' atau 'expense'.
    date dalam format 'YYYY-MM-DD'.
    """
    db: Session = get_db_session()
    try:
        trans_date = _parse_date(date)

        new_tx = Transaction(
            user_id=int(user_id),
            title=title,
            amount=float(amount),
            category=category,
            transaction_type=transaction_type,
            transaction_date=trans_date,
            note=note
        )
        db.add(new_tx)
        db.commit()
        return f"Berhasil mencatat {transaction_type} '{title}' sebesar Rp {float(amount):,.2f}."
    except Exception as e:
        db.rollback()
        return f"Gagal mencatat transaksi: {str(e)}"
    finally:
        db.close()

def get_transactions_tool(user_id: int, limit: int = 10):
    """
    Mengambil daftar transaksi terbaru untuk user tertentu.
    """
    db: Session = get_db_session()
    try:
        txs = db.query(Transaction).filter(Transaction.user_id == int(user_id)).order_by(Transaction.transaction_date.desc()).limit(limit).all()
        if not txs:
            return "Tidak ada transaksi yang ditemukan."

        return "\n".join(_format_tx_line(t) for t in txs)
    except Exception as e:
        return f"Gagal mengambil data: {str(e)}"
    finally:
        db.close()

_UPDATABLE_FIELDS = {"title", "amount", "category", "transaction_type", "note"}
_SELECTOR_KEYS = {"transaction_id", "match_title", "match_date"}
_PROTECTED_KEYS = {"id", "user_id", "created_at"}


def update_transaction_tool(
    user_id: int,
    transaction_id: Optional[int] = None,
    match_title: Optional[str] = None,
    match_date: Optional[str] = None,
    **updates,
):
    """
    Mengubah data transaksi yang sudah ada.

    Target transaksi ditentukan lewat salah satu dari:
      - transaction_id: paling pasti, dipakai bila tersedia
      - match_title dan/atau match_date: pencarian, hanya dieksekusi bila
        menghasilkan tepat satu kandidat

    Nilai baru dikirim lewat: title, amount, category, transaction_type,
    date/transaction_date, note. Perhatikan bahwa 'title' adalah nilai baru,
    sedangkan 'match_title' adalah kunci pencarian.
    """
    db: Session = get_db_session()
    try:
        tx, err = _resolve_single_transaction(db, user_id, transaction_id, match_title, match_date)
        if err:
            return err

        # Susun perubahan yang sah saja. Selector dan kolom terproteksi dibuang
        # eksplisit agar tidak pernah bocor ke setattr.
        changes = {}
        for key, value in updates.items():
            if key in _SELECTOR_KEYS or key in _PROTECTED_KEYS or value is None:
                continue
            if key in ("date", "transaction_date"):
                changes["transaction_date"] = value
            elif key in _UPDATABLE_FIELDS:
                changes[key] = value

        if not changes:
            return (
                f"Transaksi {_format_tx_line(tx)} ditemukan, tetapi tidak ada nilai baru yang diberikan. "
                f"Sebutkan apa yang ingin diubah, misalnya nominal, judul, kategori, atau tanggal."
            )

        if "amount" in changes:
            try:
                changes["amount"] = float(changes["amount"])
            except (ValueError, TypeError):
                return f"Nominal '{changes['amount']}' bukan angka yang valid."

        if "transaction_type" in changes:
            new_type = str(changes["transaction_type"]).strip().lower()
            if new_type not in ("income", "expense"):
                return f"Jenis transaksi '{changes['transaction_type']}' tidak valid. Gunakan 'income' atau 'expense'."
            changes["transaction_type"] = new_type

        if "transaction_date" in changes:
            parsed = _parse_date_strict(changes["transaction_date"])
            if parsed is None:
                # Berbeda dari create_transaction yang mundur ke hari ini: pada update,
                # menulis tanggal yang salah lebih merugikan daripada menolak perintah.
                return f"Tanggal baru '{changes['transaction_date']}' tidak dikenali. Gunakan format YYYY-MM-DD."
            changes["transaction_date"] = parsed

        before = _format_tx_line(tx)
        for key, value in changes.items():
            setattr(tx, key, value)

        db.commit()
        db.refresh(tx)
        return (
            f"Transaksi berhasil diperbarui.\n"
            f"Sebelum : {before}\n"
            f"Sesudah : {_format_tx_line(tx)}"
        )
    except Exception as e:
        db.rollback()
        return f"Gagal memperbarui transaksi: {str(e)}"
    finally:
        db.close()

def delete_transaction_tool(transaction_id: int, user_id: int):
    """
    Menghapus transaksi berdasarkan ID.
    """
    db: Session = get_db_session()
    try:
        tx = db.query(Transaction).filter(Transaction.id == int(transaction_id), Transaction.user_id == int(user_id)).first()
        if not tx:
            return "Transaksi tidak ditemukan."

        db.delete(tx)
        db.commit()
        return "Transaksi berhasil dihapus."
    except Exception as e:
        db.rollback()
        return f"Gagal menghapus transaksi: {str(e)}"
    finally:
        db.close()

def get_summary_tool(user_id: int):
    """
    Mendapatkan ringkasan keuangan (Total Income, Total Expense, dan Saldo).
    """
    db: Session = get_db_session()
    try:
        income_res = db.query(func.sum(Transaction.amount)).filter(Transaction.user_id == int(user_id), Transaction.transaction_type == 'income').scalar()
        expense_res = db.query(func.sum(Transaction.amount)).filter(Transaction.user_id == int(user_id), Transaction.transaction_type == 'expense').scalar()
        
        income = float(income_res or 0)
        expense = float(expense_res or 0)
        balance = income - expense

        return f"Ringkasan Keuangan:\n- Total Pemasukan: Rp {income:,.2f}\n- Total Pengeluaran: Rp {expense:,.2f}\n- Saldo Saat Ini: Rp {balance:,.2f}"
    except Exception as e:
        return f"Gagal menghitung ringkasan: {str(e)}"
    finally:
        db.close()

