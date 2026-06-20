"""
দোকানের হিসাব — Python Streamlit অ্যাপ
Document Service Shop Accounting App (Bengali UI)
"""

import streamlit as st
import sqlite3
import hashlib
import os
from datetime import datetime, date
from collections import defaultdict

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="দোকানের হিসাব",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DB path ──────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "dokan_hisab.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ── Init DB ──────────────────────────────────────────────────
def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            shop_name TEXT,
            owner_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS service_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            default_payment INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            transaction_date TEXT NOT NULL,
            customer_name TEXT,
            service_type_id INTEGER,
            service_type_name TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            payment INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'R',
            reference TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── Auth helpers ─────────────────────────────────────────────
def hash_pwd(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

def login_user(username: str, password: str) -> dict | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM users WHERE username=? AND password_hash=?",
        (username, hash_pwd(password)),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def register_user(username: str, password: str, shop_name: str, owner_name: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password_hash, shop_name, owner_name) VALUES (?,?,?,?)",
            (username, hash_pwd(password), shop_name, owner_name),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# ── Service type helpers ─────────────────────────────────────
def get_service_types(user_id: int) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM service_types WHERE user_id=? ORDER BY created_at",
        (user_id,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def create_service_type(user_id: int, name: str, default_payment: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO service_types (user_id, name, default_payment) VALUES (?,?,?)",
        (user_id, name, default_payment),
    )
    conn.commit()
    conn.close()

def update_service_type(sid: int, name: str, default_payment: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE service_types SET name=?, default_payment=? WHERE id=?",
        (name, default_payment, sid),
    )
    conn.commit()
    conn.close()

def delete_service_type(sid: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM service_types WHERE id=?", (sid,))
    conn.commit()
    conn.close()

# ── Transaction helpers ──────────────────────────────────────
def create_transaction(user_id: int, tx: dict):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO transactions (user_id, transaction_date, customer_name, service_type_id, service_type_name, amount, payment, status, reference, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        user_id,
        tx["transaction_date"],
        tx.get("customer_name") or None,
        tx.get("service_type_id") or None,
        tx["service_type_name"],
        int(tx["amount"]),
        int(tx["payment"]),
        tx["status"],
        tx.get("reference") or None,
        tx.get("notes") or None,
    ))
    conn.commit()
    conn.close()

def get_transactions(
    user_id: int,
    from_date: str | None = None,
    to_date: str | None = None,
    service_type_id: int | None = None,
    status: str | None = None,
    search_name: str | None = None,
) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    sql = "SELECT * FROM transactions WHERE user_id=?"
    params = [user_id]
    if from_date:
        sql += " AND transaction_date >= ?"
        params.append(from_date)
    if to_date:
        sql += " AND transaction_date <= ?"
        params.append(to_date)
    if service_type_id:
        sql += " AND service_type_id = ?"
        params.append(service_type_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if search_name:
        sql += " AND customer_name LIKE ?"
        params.append(f"%{search_name}%")
    sql += " ORDER BY transaction_date DESC, created_at DESC LIMIT 500"
    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def update_transaction(tid: int, tx: dict):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE transactions
        SET transaction_date=?, customer_name=?, service_type_name=?, amount=?, payment=?, status=?, reference=?, notes=?
        WHERE id=?
    """, (
        tx["transaction_date"],
        tx.get("customer_name") or None,
        tx["service_type_name"],
        int(tx["amount"]),
        int(tx["payment"]),
        tx["status"],
        tx.get("reference") or None,
        tx.get("notes") or None,
        tid,
    ))
    conn.commit()
    conn.close()

def delete_transaction(tid: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM transactions WHERE id=?", (tid,))
    conn.commit()
    conn.close()

# ── Dashboard helpers ──────────────────────────────────────────
def get_today_summary(user_id: int) -> dict:
    today = date.today().isoformat()
    rows = get_transactions(user_id, from_date=today, to_date=today)
    total_income = sum(r["amount"] or 0 for r in rows)
    total_payment = sum(r["payment"] or 0 for r in rows)
    unpaid = sum(r["amount"] or 0 for r in rows if r["status"] == "P")
    return {
        "total_income": total_income,
        "total_payment": total_payment,
        "count": len(rows),
        "unpaid_amount": unpaid,
    }

def get_monthly_summary(user_id: int, year: int, month: int) -> dict:
    from_date = f"{year:04d}-{month:02d}-01"
    last_day = (datetime(year, month % 12 + 1, 1) - __import__("datetime").timedelta(days=1)).day
    to_date = f"{year:04d}-{month:02d}-{last_day:02d}"
    rows = get_transactions(user_id, from_date=from_date, to_date=to_date)
    total_income = sum(r["amount"] or 0 for r in rows)
    total_payment = sum(r["payment"] or 0 for r in rows)
    unpaid = sum(r["amount"] or 0 for r in rows if r["status"] == "P")
    return {
        "total_income": total_income,
        "total_payment": total_payment,
        "count": len(rows),
        "unpaid_amount": unpaid,
    }

# ── UI helpers ─────────────────────────────────────────────────
STATUS_LABELS = {"A": "অগ্রিম", "P": "বাকি", "R": "পেইড"}

def fmt_tk(n: int) -> str:
    return f"৳ {n:,.0f}"

def fmt_dt(d: str) -> str:
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return d

# ── Auth state ─────────────────────────────────────────────────
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "dashboard"

# ═══════════════════════════════════════════════════════════════
# LOGIN / REGISTER
# ═══════════════════════════════════════════════════════════════
def auth_page():
    st.title("📋 দোকানের হিসাব")
    st.caption("Document Service Shop Accounting")
    tab1, tab2 = st.tabs(["🔑 লগইন", "📝 নতুন অ্যাকাউন্ট"])
    with tab1:
        u = st.text_input("ইউজারনেম", key="login_u")
        p = st.text_input("পাসওয়ার্ড", type="password", key="login_p")
        if st.button("লগইন করুন", use_container_width=True):
            user = login_user(u, p)
            if user:
                st.session_state.user = user
                st.success("সফলভাবে লগইন হয়েছে!")
                st.rerun()
            else:
                st.error("ভুল ইউজারনেম বা পাসওয়ার্ড")
    with tab2:
        u2 = st.text_input("ইউজারনেম", key="reg_u")
        p2 = st.text_input("পাসওয়ার্ড", type="password", key="reg_p")
        shop = st.text_input("দোকানের নাম", key="reg_shop")
        owner = st.text_input("মালিকের নাম", key="reg_owner")
        if st.button("অ্যাকাউন্ট তৈরি করুন", use_container_width=True):
            if register_user(u2, p2, shop, owner):
                st.success("অ্যাকাউন্ট তৈরি হয়েছে! লগইন করুন।")
            else:
                st.error("ইউজারনেম আগে থেকেই আছে")

# ═══════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════
def dashboard_page():
    st.title("📊 ড্যাশবোর্ড")
    uid = st.session_state.user["id"]
    today = get_today_summary(uid)
    now = datetime.now()
    monthly = get_monthly_summary(uid, now.year, now.month)
    unpaid_all = get_transactions(uid, status="P")
    
    # Quick actions
    c1, c2 = st.columns(2)
    if c1.button("➕ নতুন লেনদেন", use_container_width=True):
        st.session_state.page = "add"
        st.rerun()
    if c2.button("📋 সব লেনদেন", use_container_width=True):
        st.session_state.page = "history"
        st.rerun()
        
    st.divider()
    # Today's summary
    st.subheader("আজকের সারসংক্ষেপ")
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("মোট আয়", fmt_tk(today["total_income"]))
    t2.metric("মোট লেনদেন", f"{today['count']}টি")
    t3.metric("লাভ", fmt_tk(today["total_income"] - today["total_payment"]))
    with t4:
        st.metric("বাকি (ক্লিক করুন)", fmt_tk(today["unpaid_amount"]))
        if st.button("আজকের বাকি দেখুন", key="btn_today_unpaid"):
            today_unpaid = [r for r in unpaid_all if r["transaction_date"] == date.today().isoformat()]
            if today_unpaid:
