"""
দোকানের হিসাব — Python Streamlit অ্যাপ
Document Service Shop Accounting App (Bengali UI)
"""

import streamlit as st
import sqlite3
import hashlib
import os
import calendar
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
            received_amount INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'R',
            reference TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 🌟 স্পেশাল রিকভারি লজিক: আপনার পুরনো আইডির পাসওয়ার্ডটি নতুন হ্যাশ দিয়ে আপডেট করা হচ্ছে
    try:
        target_user = "rafimhr561@gmail.com"
        target_hash = hashlib.sha256("r@fi5596".encode()).hexdigest()
        
        # ইউজার অলরেডি থাকলে তার পাসওয়ার্ড হ্যাশ নতুন সিস্টেমে জোরপূর্বক আপডেট করা হবে
        c.execute("SELECT id FROM users WHERE LOWER(username)=LOWER(?)", (target_user,))
        user_row = c.fetchone()
        if user_row:
            c.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (target_hash, user_row["id"])
            )
        else:
            # যদি কোনো কারণে ডিলিট হয়ে থাকে তবে নতুন করে তৈরি হবে
            c.execute(
                "INSERT INTO users (username, password_hash, shop_name, owner_name) VALUES (?, ?, 'আমার দোকান', 'রাফি')",
                (target_user, target_hash)
            )
    except Exception as e:
        pass

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
        "SELECT * FROM users WHERE LOWER(username)=LOWER(?) AND password_hash=?",
        (username.strip(), hash_pwd(password)),
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
            (username.strip(), hash_pwd(password), shop_name, owner_name),
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
        INSERT INTO transactions (user_id, transaction_date, customer_name, service_type_id, service_type_name, amount, payment, received_amount, status, reference, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        user_id,
        tx["transaction_date"],
        tx.get("customer_name") or "----",
        tx.get("service_type_id") or None,
        tx["service_type_name"],
        int(tx["amount"]),
        int(tx["payment"]),
        int(tx["received_amount"]),
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
        SET transaction_date=?, customer_name=?, service_type_name=?, amount=?, payment=?, received_amount=?, status=?, reference=?, notes=?
        WHERE id=?
    """, (
        tx["transaction_date"],
        tx.get("customer_name") or "----",
        tx["service_type_name"],
        int(tx["amount"]),
        int(tx["payment"]),
        int(tx["received_amount"]),
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
def calculate_summary(rows: list[dict]) -> dict:
    total_income = sum(r["amount"] or 0 for r in rows)
    total_payment = sum(r["payment"] or 0 for r in rows)
    net_profit = total_income - total_payment
    
    unpaid = 0
    for r in rows:
        bill = r["amount"] or 0
        rec = r["received_amount"] if r["received_amount"] is not None else (bill if r["status"] == "R" else 0)
        if bill > rec:
            unpaid += (bill - rec)
            
    return {
        "total_income": total_income,
        "total_payment": total_payment,
        "net_profit": net_profit,
        "unpaid_amount": unpaid,
        "count": len(rows),
    }

def get_today_summary(user_id: int) -> dict:
    today = date.today().isoformat()
    rows = get_transactions(user_id, from_date=today, to_date=today)
    return calculate_summary(rows)

def get_monthly_summary(user_id: int, year: int, month: int) -> dict:
    last_day = calendar.monthrange(year, month)[1]
    from_date = f"{year:04d}-{month:02d}-01"
    to_date = f"{year:04d}-{month:02d}-{last_day:02d}"
    rows = get_transactions(user_id, from_date=from_date, to_date=to_date)
    return calculate_summary(rows)

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

def set_page(page_name: str):
    st.session_state.page = page_name
    st.query_params["p"] = page_name

# ── Auth state ─────────────────────────────────────────────────
if "user" not in st.session_state:
    st.session_state.user = None

url_params = st.query_params
if "p" in url_params:
    st.session_state.page = url_params["p"]
elif "page" not in st.session_state:
    st.session_state.page = "dashboard"

# ═══════════════════════════════════════════════════════════════
# LOGIN / REGISTER
# ═══════════════════════════════════════════════════════════════
def auth_page():
    st.title("📋  দোকানের হিসাব")
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
                set_page("dashboard")
                st.rerun()
            else:
                st.error("ভুল ইউজারনেম বা পাসওয়ার্ড! (ইউজারনেম ছোট/বড় হাতের অক্ষর ঠিক আছে কি না চেক করুন)")
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
    unpaid_all = get_transactions(uid)
    
    c1, c2 = st.columns(2)
    if c1.button("➕ নতুন লেনদেন", use_container_width=True):
        set_page("add")
        st.rerun()
    if c2.button("📋 সব লেনদেন", use_container_width=True):
        set_page("history")
        st.rerun()
        
    st.divider()
    st.subheader("আজকের সারসংক্ষেপ")
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("মোট টাকা (আয়)", fmt_tk(today["total_income"]))
    t2.metric("মোট লেনদেন", f"{today['count']} টি")
    t3.metric("লাভ (টাকা - পেমেন্ট)", fmt_tk(today["net_profit"]))
    with t4:
        st.metric("বাকি (ক্লিক করুন)", fmt_tk(today["unpaid_amount"]))
        if st.button("আজকের বাকি দেখুন", key="btn_today_unpaid"):
            today_str = date.today().isoformat()
            today_unpaid = []
            for r in unpaid_all:
                if r["transaction_date"] == today_str:
                    rec = r["received_amount"] if r["received_amount"] is not None else (r["amount"] if r["status"] == "R" else 0)
                    if r["amount"] > rec:
                        today_unpaid.append((r, r["amount"] - rec))
            if today_unpaid:
                st.write("**আজকের বাকি লেনদেন:**")
                for r, due in today_unpaid:
                    st.write(f"- {r['customer_name'] or '----'} | {r['service_type_name']} | মোট: {fmt_tk(r['amount'])} | বাকি: {fmt_tk(due)}")
            else:
                st.info("আজ কোনো বাকি লেনদেন নেই")
                
    st.divider()
    st.subheader("চলতি মাসের সারসংক্ষেপ")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("মোট টাকা (আয়)", fmt_tk(monthly["total_income"]))
    m2.metric("মোট লেনদেন", f"{monthly['count']} টি")
    m3.metric("লাভ (টাকা - পেমেন্ট)", fmt_tk(monthly["net_profit"]))
    with m4:
        st.metric("বাকি (ক্লিক করুন)", fmt_tk(monthly["unpaid_amount"]))
        if st.button("মাসের বাকি দেখুন", key="btn_month_unpaid"):
            monthly_unpaid = []
            for r in unpaid_all:
                rec = r["received_amount"] if r["received_amount"] is not None else (r["amount"] if r["status"] == "R" else 0)
                if r["amount"] > rec:
                    monthly_unpaid.append((r, r["amount"] - rec))
            if monthly_unpaid:
                st.write("**চলতি বকেয়া লেনদেনসমূহ:**")
                for r, due in monthly_unpaid:
                    st.write(f"- {fmt_dt(r['transaction_date'])} | {r['customer_name'] or '----'} | বাকি: {fmt_tk(due)} (মোট: {fmt_tk(r['amount'])})")
            else:
                st.info("কোনো বকেয়া লেনদেন নেই")

# ═══════════════════════════════════════════════════════════════
# ADD TRANSACTION
# ═══════════════════════════════════════════════════════════════
def add_transaction_page():
    st.title("➕ নতুন লেনদেন যোগ করুন")
    uid = st.session_state.user["id"]
    services = get_service_types(uid)
    with st.form("tx_form"):
        tx_date = st.date_input("তারিখ", value=date.today())
        name = st.text_input("গ্রাহকের নাম (ঐচ্ছিক)")
        reference = st.selectbox("রেফারেন্স", ["A", "R", "P"])
        
        service_options = [s["name"] for s in services]
        service_options.append("+ অন্যান্য (ম্যানুয়ালি লিখুন)")
        selected = st.selectbox("সেবা ধরন", service_options)
        
        if selected == "+ অন্যান্য (ম্যানুয়ালি লিখুন)":
            service_name = st.text_input("সেবার নাম লিখুন")
            payment = st.number_input("পেমেন্ট (খরচ)", min_value=0, value=0)
        else:
            service_name = selected
            default_pay = next((s["default_payment"] for s in services if s["name"] == selected), 0)
            payment = st.number_input("পেমেন্ট (খরচ)", min_value=0, value=default_pay)
            
        amount = st.number_input("টাকা (আয়)", min_value=0, value=0)
        status = st.selectbox("স্ট্যাটাস", [("R", "পেইড"), ("P", "বাকি"), ("A", "অগ্রিম")], format_func=lambda x: x[1])
        notes = st.text_area("নোট (ঐচ্ছিক)")
        
        submitted = st.form_submit_button("💾 সংরক্ষণ করুন", use_container_width=True)
        if submitted:
            if not service_name:
                st.error("সেবার নাম দিন")
            else:
                final_name = name.strip() if name.strip() else "----"
                received_calc = amount if status[0] == "R" else 0
                if status[0] == "A":
                    received_calc = amount
                
                sid = next((s["id"] for s in services if s["name"] == selected), None)
                create_transaction(uid, {
                    "transaction_date": tx_date.isoformat(),
                    "customer_name": final_name,
                    "service_type_id": sid,
                    "service_type_name": service_name,
                    "amount": amount,
                    "payment": payment,
                    "received_amount": received_calc,
                    "status": status[0],
                    "reference": reference,
                    "notes": notes,
                })
                st.success("লেনদেন সংরক্ষিত হয়েছে!")
                st.balloons()
    if st.button("← ড্যাশবোর্ডে ফিরুন", use_container_width=True):
        set_page("dashboard")
        st.rerun()

# ═══════════════════════════════════════════════════════════════
# TRANSACTION HISTORY
# ═══════════════════════════════════════════════════════════════
def history_page():
    st.title("📋  লেনদেনের তালিকা")
    uid = st.session_state.user["id"]
    services = get_service_types(uid)
    with st.expander("🔍 ফিল্টার", expanded=False):
        f1, f2, f3, f4 = st.columns(4)
        from_d = f1.date_input("শুরুর তারিখ", value=None)
        to_d = f2.date_input("শেষ তারিখ", value=None)
        svc = f3.selectbox("সেবা ধরন", ["সব"] + [s["name"] for s in services])
        sts = f4.selectbox("স্ট্যাটাস", ["সব", "অগ্রিম", "বাকি", "পেইড"])
        search = st.text_input("নাম দিয়ে খুঁজুন")
        
    rows = get_transactions(
        uid,
        from_date=from_d.isoformat() if from_d else None,
        to_date=to_d.isoformat() if to_d else None,
        service_type_id=next((s["id"] for s in services if s["name"] == svc), None) if svc != "সব" else None,
        status={"অগ্রিম": "A", "বাকি": "P", "পেইড": "R"}.get(sts),
        search_name=search or None,
    )
    
    total_bill_sum = sum(r["amount"] or 0 for r in rows)
    total_pay_sum = sum(r["payment"] or 0 for r in rows)
    st.info(f"মোট টাকা (আয়): {fmt_tk(total_bill_sum)} | মোট পেমেন্ট (খরচ): {fmt_tk(total_pay_sum)} | লেনদেন: {len(rows)}টি")
    
    if not rows:
        st.warning("কোনো লেনদেন পাওয়া যায়নি")
    else:
        for r in rows:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{fmt_dt(r['transaction_date'])}** — {r['customer_name'] or '----'}")
                c1.caption(f"কাজ: {r['service_type_name']} | রেফ: {r['reference'] or '----'}")
                
                c2.write(f"টাকা (আয়): **{fmt_tk(r['amount'])}**")
                c2.write(f"পেমেন্ট (খরচ): {fmt_tk(r['payment'])}")
                
                status_color = {"A": "blue", "P": "red", "R": "green"}.get(r["status"], "gray")
                c3.markdown(f":{status_color}[**{STATUS_LABELS.get(r['status'], r['status'])}**]")
                
                with st.popover("⚙️ কার্যক্রম"):
                    if st.button("✏️ সম্পাদনা", key=f"edit_{r['id']}"):
                        st.session_state.edit_tx = r
                        set_page("edit")
                        st.rerun()
                    if st.button("🗑️ মুছুন", key=f"del_{r['id']}"):
                        delete_transaction(r["id"])
                        st.success("মুছে ফেলা হয়েছে")
                        st.rerun()
                        
    if st.button("← ড্যাশবোর্ডে ফিরুন", use_container_width=True):
        set_page("dashboard")
        st.rerun()

# ── EDIT TRANSACTION ───────────────────────────────────────────
def edit_page():
    st.title("✏️ লেনদেন সম্পাদনা")
    uid = st.session_state.user["id"]
    tx = st.session_state.get("edit_tx")
    if not tx:
        st.error("কোনো লেনদেন নির্বাচন করা হয়নি")
        return
        
    with st.form("edit_form"):
        tx_date = st.date_input("তারিখ", value=datetime.strptime(tx["transaction_date"], "%Y-%m-%d").date())
        name = st.text_input("গ্রাহকের নাম (ঐচ্ছিক)", value=tx["customer_name"] if tx["customer_name"] != "----" else "")
        ref_idx = ["A", "R", "P"].index(tx["reference"]) if tx["reference"] in ["A", "R", "P"] else 0
        reference = st.selectbox("রেফারেন্স", ["A", "R", "P"], index=ref_idx)
        
        svc_name = st.text_input("সেবার নাম", value=tx["service_type_name"])
        amount = st.number_input("টাকা (আয়)", min_value=0, value=int(tx["amount"]))
        payment = st.number_input("পেমেন্ট (খরচ)", min_value=0, value=int(tx["payment"]))
        
        status = st.selectbox(
            "স্ট্যাটাস",
            [("R", "পেইড"), ("P", "বাকি"), ("A", "অগ্রিম")],
            index={"R": 0, "P": 1, "A": 2}.get(tx["status"], 0),
            format_func=lambda x: x[1],
        )
        notes = st.text_area("নোট", value=tx["notes"] or "")
        
        if st.form_submit_button("💾  হালনাগাদ করুন", use_container_width=True):
            final_name = name.strip() if name.strip() else "----"
            received_calc = amount if status[0] == "R" else 0
            if status[0] == "A":
                received_calc = amount
                
            update_transaction(tx["id"], {
                "transaction_date": tx_date.isoformat(),
                "customer_name": final_name,
                "service_type_name": svc_name,
                "amount": amount,
                "payment": payment,
                "received_amount": received_calc,
                "status": status[0],
                "reference": reference,
                "notes": notes,
            })
            st.success("হালনাগাদ হয়েছে!")
            set_page("history")
            st.rerun()
            
    if st.button("❌ বাতিল", use_container_width=True):
        set_page("history")
        st.rerun()

# ── SERVICE TYPES ──────────────────────────────────────────────
def service_types_page():
    st.title("🔧  সেবা ধরন")
    uid = st.session_state.user["id"]
    services = get_service_types(uid)
    st.subheader("নতুন সেবা ধরন যোগ করুন")
    with st.form("svc_form"):
        n = st.text_input("সেবার নাম")
        p = st.number_input("ডিফল্ট পেমেন্ট", min_value=0, value=0)
        if st.form_submit_button("➕ যোগ করুন", use_container_width=True):
            if n:
                create_service_type(uid, n, int(p))
                st.success("যোগ হয়েছে!")
                st.rerun()
            else:
                st.error("নাম দিন")
                
    st.subheader("বিদ্যমান সেবা ধরন")
    if not services:
        st.info("কোনো সেবা ধরন নেই")
    else:
        for s in services:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{s['name']}**")
                c2.write(f"ডিফল্ট পেমেন্ট: {fmt_tk(s['default_payment'])}")
                with c3:
                    with st.popover("⚙️"):
                        new_name = st.text_input("নাম", value=s["name"], key=f"sn_{s['id']}")
                        new_pay = st.number_input("পেমেন্ট", min_value=0, value=s["default_payment"], key=f"sp_{s['id']}")
                        if st.button("💾 সংরক্ষণ", key=f"ss_{s['id']}"):
                            update_service_type(s["id"], new_name, int(new_pay))
                            st.success("হালনাগাদ হয়েছে")
                            st.rerun()
                        if st.button("🗑️ মুছুন", key=f"sd_{s['id']}"):
                            delete_service_type(s["id"])
                            st.success("মুছে ফেলা হয়েছে")
                            st.rerun()
                            
    if st.button("← ড্যাশবোর্ডে ফিরুন", use_container_width=True):
        set_page("dashboard")
        st.rerun()

# ── REPORTS ───────────────────────────────────────────────────
def reports_page():
    st.title("📈  রিপোর্ট ও সারসংক্ষেপ")
    uid = st.session_state.user["id"]
    now = datetime.now()
    year = st.selectbox("বছর", list(range(2024, 2028)), index=now.year - 2024)
    month = st.selectbox("মাস", list(range(1, 13)), index=now.month - 1)
    
    last_day = calendar.monthrange(year, month)[1]
    from_date = f"{year:04d}-{month:02d}-01"
    to_date = f"{year:04d}-{month:02d}-{last_day:02d}"
    
    rows = get_transactions(uid, from_date=from_date, to_date=to_date)
    summary = calculate_summary(rows)
    
    st.divider()
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("মোট টাকা (আয়)", fmt_tk(summary["total_income"]))
    r2.metric("মোট পেমেন্ট (খরচ)", fmt_tk(summary["total_payment"]))
    r3.metric("লাভ (টাকা - পেমেন্ট)", fmt_tk(summary["net_profit"]))
    r4.metric("বাকি", fmt_tk(summary["unpaid_amount"]))
    st.divider()
    
    st.subheader("কাজ অনুযায়ী বিভাজন")
    svc_map = defaultdict(lambda: {"count": 0, "income": 0, "payment": 0})
    for r in rows:
        svc_map[r["service_type_name"]]["count"] += 1
        svc_map[r["service_type_name"]]["income"] += r["amount"] or 0
        svc_map[r["service_type_name"]]["payment"] += r["payment"] or 0
        
    if svc_map:
        data = []
        for name, v in svc_map.items():
            data.append({
                "কাজ": name,
                "সংখ্যা": v["count"],
                "মোট টাকা (আয়)": fmt_tk(v["income"]),
                "মোট পেমেন্ট (খরচ)": fmt_tk(v["payment"]),
                "লাভ": fmt_tk(v["income"] - v["payment"]),
            })
        st.dataframe(data, use_container_width=True, hide_index=True)
    else:
        st.info("কোনো তথ্য নেই")
        
    st.divider()
    st.subheader("তারিখ অনুযায়ী বিভাজন")
    day_map = defaultdict(lambda: {"count": 0, "income": 0, "payment": 0})
    for r in rows:
        day_map[r["transaction_date"]]["count"] += 1
        day_map[r["transaction_date"]]["income"] += r["amount"] or 0
        day_map[r["transaction_date"]]["payment"] += r["payment"] or 0
        
    if day_map:
        data2 = []
        for d, v in sorted(day_map.items(), reverse=True):
            data2.append({
                "তারিখ": fmt_dt(d),
                "লেনদেন": v["count"],
                "মোট টাকা (আয়)": fmt_tk(v["income"]),
                "মোট পেমেন্ট (খরচ)": fmt_tk(v["payment"]),
                "লাভ": fmt_tk(v["income"] - v["payment"]),
            })
        st.dataframe(data2, use_container_width=True, hide_index=True)
    else:
        st.info("কোনো তথ্য নেই")
        
    if st.button("← ড্যাশবোর্ডে ফিরুন", use_container_width=True):
        set_page("dashboard")
        st.rerun()

# ── MAIN NAV ───────────────────────────────────────────────────
def main():
    if not st.session_state.user:
        auth_page()
        return
        
    with st.sidebar:
        st.title("📋  দোকানের হিসাব")
        st.caption(f"{st.session_state.user.get('shop_name') or 'দোকান'}")
        st.divider()
        pages = {
            "dashboard": "📊 ড্যাশবোর্ড",
            "add": "➕ লেনদেন যোগ",
            "history": "📋 লেনদেন তালিকা",
            "services": "🔧  সেবা ধরন",
            "reports": "📈  রিপোর্ট",
        }
        for key, label in pages.items():
            if st.button(label, use_container_width=True, key=f"nav_{key}"):
                set_page(key)
                st.rerun()
        st.divider()
        if st.button("🚪 লগআউট", use_container_width=True):
            st.session_state.user = None
            set_page("dashboard")
            st.rerun()
            
    page = st.session_state.page
    if page == "dashboard":
        dashboard_page()
    elif page == "add":
        add_transaction_page()
    elif page == "history":
        history_page()
    elif page == "edit":
        edit_page()
    elif page == "services":
        service_types_page()
    elif page == "reports":
        reports_page()
    else:
        dashboard_page()

if __name__ == "__main__":
    main()
