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

_TYPE_ALIASES = {
    "income": "income", "pemasukan": "income", "masuk": "income",
    "expense": "expense", "pengeluaran": "expense", "keluar": "expense",
}
_TYPE_LABEL = {"income": "pemasukan", "expense": "pengeluaran"}


def get_transactions_tool(
    user_id: int,
    limit: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    transaction_type: Optional[str] = None,
):
    """
    Mengambil daftar transaksi user, terbaru lebih dulu.

    Filter opsional:
      - start_date / end_date (YYYY-MM-DD, inklusif). Jika hanya start_date yang
        diisi, dianggap satu hari saja, sehingga "pengeluaran tanggal 29" cukup
        dengan start_date.
      - transaction_type: 'income' atau 'expense' (alias Indonesia diterima).

    Filter dikerjakan di database, bukan diserahkan ke model. Model kecil sering
    salah memilah daftar campuran, dan cenderung menjawab dengan transaksi lain
    ketika yang ditanyakan sebenarnya tidak ada.
    """
    db: Session = get_db_session()
    try:
        # Query dasar: hanya transaksi milik user ini. Semua filter menempel ke sini.
        base = db.query(Transaction).filter(Transaction.user_id == int(user_id))

        # Tanpa filter: output identik dengan versi lama, agar hasil benchmark lama
        # tetap bisa dibandingkan untuk pertanyaan "tampilkan transaksi saya".
        has_filter = bool(start_date or end_date or transaction_type)
        if not has_filter:
            # Ambil N transaksi terbaru (urut tanggal menurun), lalu format jadi teks.
            txs = base.order_by(Transaction.transaction_date.desc()).limit(limit).all()
            if not txs:
                return "Tidak ada transaksi yang ditemukan."
            return "\n".join(_format_tx_line(t) for t in txs)

        # --- Validasi filter. Input tidak valid ditolak, bukan diabaikan diam-diam,
        # karena mengabaikan filter berarti menjawab pertanyaan yang berbeda.
        tx_type = None
        if transaction_type:
            tx_type = _TYPE_ALIASES.get(str(transaction_type).strip().lower())
            if tx_type is None:
                return f"Jenis transaksi '{transaction_type}' tidak valid. Gunakan 'income' atau 'expense'."

        start = _parse_date_strict(start_date) if start_date else None
        end = _parse_date_strict(end_date) if end_date else None
        if start_date and start is None:
            return f"Tanggal mulai '{start_date}' tidak dikenali. Gunakan format YYYY-MM-DD."
        if end_date and end is None:
            return f"Tanggal akhir '{end_date}' tidak dikenali. Gunakan format YYYY-MM-DD."
        if start and not end:
            end = start  # hanya satu tanggal -> satu hari
        if start and end and start > end:
            start, end = end, start

        # Terapkan filter tanggal. date_q = query dengan filter tanggal saja
        # (dipakai lagi di bawah untuk menghitung "ada berapa jenis lain").
        date_q = base
        if start:
            # >= awal hari start (jam 00:00)
            date_q = date_q.filter(Transaction.transaction_date >= start.replace(hour=0, minute=0, second=0, microsecond=0))
        if end:
            # < awal hari BERIKUTNYA setelah end, supaya tanggal 'end' ikut terhitung penuh
            date_q = date_q.filter(Transaction.transaction_date < end.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))

        # query = date_q + filter jenis (kalau diminta). Inilah hasil akhir yang dihitung.
        query = date_q.filter(Transaction.transaction_type == tx_type) if tx_type else date_q

        # --- Deskripsi filter untuk kalimat jawaban
        if start and end and start.date() == end.date():
            period = f"pada tanggal {start.strftime('%Y-%m-%d')}"
        elif start and end:
            period = f"pada {start.strftime('%Y-%m-%d')} s.d. {end.strftime('%Y-%m-%d')}"
        elif end:
            period = f"sampai {end.strftime('%Y-%m-%d')}"
        else:
            period = ""
        kind = _TYPE_LABEL[tx_type] if tx_type else "transaksi"
        scope = f"{kind} {period}".strip()

        # matched = berapa transaksi yang cocok filter. Dihitung di DB (cepat & akurat).
        matched = query.count()
        if matched == 0:
            # Jawaban tegas "tidak ada" — ini kunci perbaikan kasus "pengeluaran tgl 29".
            msg = f"Tidak ada {scope}."
            # Beri tahu apa yang sebenarnya ada pada periode itu, supaya model tidak
            # tergoda mengisi jawaban dengan transaksi dari tanggal lain.
            if tx_type and period:
                other = date_q.filter(Transaction.transaction_type != tx_type).count()
                if other:
                    other_label = _TYPE_LABEL["income" if tx_type == "expense" else "expense"]
                    msg += f" Pada periode tersebut hanya ada {other} {other_label}."
            return msg

        # Total dihitung di database atas SELURUH hasil filter, bukan hanya baris yang
        # ditampilkan. Model 3B rawan salah menjumlahkan, jadi angkanya diberikan jadi.
        # Hitung total nominal per jenis LANGSUNG di database (SUM + GROUP BY),
        # bukan dijumlahkan oleh model yang rawan salah hitung.
        totals = dict(
            query.with_entities(Transaction.transaction_type, func.sum(Transaction.amount))
            .group_by(Transaction.transaction_type)
            .all()
        )
        # Ambil barisnya (dibatasi limit) untuk ditampilkan. Total di atas tetap
        # mencakup SEMUA yang cocok, bukan cuma yang ditampilkan.
        txs = query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).limit(limit).all()

        # Rakit header ringkasan: jumlah transaksi + total per jenis.
        header = [f"Ditemukan {matched} {scope}."]
        for t_type in ("expense", "income"):
            if t_type in totals:
                header.append(f"Total {_TYPE_LABEL[t_type]}: Rp {float(totals[t_type] or 0):,.2f}")
        if matched > len(txs):
            # Jujur beri tahu kalau ada baris yang tidak ditampilkan karena limit.
            header.append(f"Menampilkan {len(txs)} dari {matched} transaksi (dibatasi limit={limit}).")

        # Gabung header + daftar transaksi jadi satu teks balasan.
        return "\n".join(header) + "\n" + "\n".join(_format_tx_line(t) for t in txs)
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

