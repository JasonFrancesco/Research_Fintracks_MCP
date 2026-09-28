import sys
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List, Optional

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

        result = []
        for t in txs:
            d_str = t.transaction_date.strftime('%Y-%m-%d') if hasattr(t.transaction_date, 'strftime') else str(t.transaction_date)[:10]
            result.append(f"[{t.id}] {d_str} | {t.title} | {t.category} | {t.transaction_type}: Rp {float(t.amount):,.2f}")
        return "\n".join(result)
    except Exception as e:
        return f"Gagal mengambil data: {str(e)}"
    finally:
        db.close()

def update_transaction_tool(transaction_id: int, user_id: int, **updates):
    """
    Mengubah data transaksi yang sudah ada.
    Parameter updates bisa berupa: title, amount, category, transaction_type, date/transaction_date, note.
    """
    db: Session = get_db_session()
    try:
        tx = db.query(Transaction).filter(Transaction.id == int(transaction_id), Transaction.user_id == int(user_id)).first()
        if not tx:
            return "Transaksi tidak ditemukan atau Anda tidak punya akses."

        for key, value in updates.items():
            if key in ["date", "transaction_date"]:
                tx.transaction_date = _parse_date(value)
            elif key == "amount":
                tx.amount = float(value)
            elif hasattr(tx, key):
                setattr(tx, key, value)

        db.commit()
        return "Transaksi berhasil diperbarui."
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

