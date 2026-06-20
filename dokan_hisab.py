"""
দোকানের হিসাব — Google Sheets লাইভ কানেকশন অ্যাপ
Document Service Shop Accounting App (Live Google Sheets)
"""

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
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

# ── Google Sheets Connection ─────────────────────────────────
# এটি সরাসরি আপনার Streamlit Secrets থেকে credentials নিয়ে কানেক্ট হবে
conn = st.connection("gsheets", type=GSheetsConnection)

def get_all_transactions() -> pd.DataFrame:
    """গুগল শিট থেকে সব ডেটা রিড করার ফাংশন"""
    try:
        df = conn.read(ttl="1s") # প্রতি সেকেন্ডে ফ্রেশ ডেটা আনবে
        # যদি শিট খালি থাকে বা কলাম না থাকে
        if df.empty or "transaction_date" not in df.columns:
            return pd.DataFrame(columns=[
                "id", "transaction_date", "customer_name", "service_type_name", 
                "amount", "payment", "received_amount", "status", "reference", "notes"
            ])
        return df
    except Exception:
        return pd.DataFrame(columns=[
            "id", "transaction_date", "customer_name", "service_type_name", 
            "amount", "payment", "received_amount", "status", "reference", "notes"
        ])

def save_transaction(new_tx: dict):
    """গুগল শিটে নতুন লেনদেন যোগ করার ফাংশন"""
    df = get_all_transactions()
    
    # নতুন আইডি জেনারেট করা
    new_id = int(df["id"].max() + 1) if not df.empty and pd.notna(df["id"].max()) else 1
    new_tx["id"] = new_id
    
    # নতুন ডেটা যুক্ত করা
    new_row = pd.DataFrame([new_tx])
    updated_df = pd.concat([df, new_row], ignore_index=True)
    
    # গুগল শিটে রাইট করা
    conn.update(data=updated_df)
    st.cache_data.clear()

# ── Dashboard helpers ──────────────────────────────────────────
def calculate_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total_income": 0, "total_payment": 0, "total_received": 0, "net_profit": 0, "unpaid_amount": 0, "count": 0}
        
    total_bill = pd.to_numeric(df["amount"]).sum()
    total_cost = pd.to_numeric(df["payment"]).sum()
    total_received = pd.to_numeric(df["received_amount"]).sum()
    
    net_profit = total_bill - total_cost
    
    # বাকি হিসাব
    df["due"] = pd.to_numeric(df["amount"]) - pd.to_numeric(df["received_amount"])
    unpaid = df[df["due"] > 0]["due"].sum()
    
    return {
        "total_income": total_bill,
        "total_payment": total_cost,
        "total_received": total_received,
        "net_profit": net_profit,
        "unpaid_amount": unpaid,
        "count": len(df),
    }

# ── UI helpers ─────────────────────────────────────────────────
STATUS_LABELS = {"A": "অগ্রিম", "P": "বাকি", "R": "পেইড"}

def fmt_tk(n: float) -> str:
    return f"৳ {int(n):,.0f}"

def fmt_dt(d: str) -> str:
    try:
        dt = datetime.strptime(str(d)[:10], "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return str(d)

# ── State Management ───────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "dashboard"

# ═══════════════════════════════════════════════════════════════
# DASHBOARD PAGE
# ═══════════════════════════════════════════════════════════════
def dashboard_page():
    st.title("📊 ড্যাশবোর্ড (Live Cloud Sync)")
    
    df = get_all_transactions()
    today_str = date.today().isoformat()
    
    # ফিল্টারড ডেটাফ্রেম তৈরি
    df_today = df[df["transaction_date"] == today_str] if not df.empty else pd.DataFrame()
    
    now = datetime.now()
    current_month_prefix = f"{now.year:04d}-{now.month:02d}"
    df_month = df[df["transaction_date"].str.startswith(current_month_prefix, na=False)] if not df.empty else pd.DataFrame()
    
    today = calculate_summary(df_today)
    monthly = calculate_summary(df_month)
    
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
    t1.metric("মোট বিক্রি (বিল)", fmt_tk(today["total_income"]))
    t2.metric("নগদ আদায়", fmt_tk(today["total_received"]))
    t3.metric("প্রকৃত লাভ", fmt_tk(today["net_profit"]))
    t4.metric("আজকের বাকি", fmt_tk(today["unpaid_amount"]))
                
    st.divider()
    # Monthly summary
    st.subheader("চলতি মাসের সারসংক্ষেপ")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("মোট বিক্রি (বিল)", fmt_tk(monthly["total_income"]))
    m2.metric("নগদ আদায়", fmt_tk(monthly["total_received"]))
    m3.metric("প্রকৃত লাভ", fmt_tk(monthly["net_profit"]))
    m4.metric("মোট বকেয়া বাকি", fmt_tk(monthly["unpaid_amount"]))

# ═══════════════════════════════════════════════════════════════
# ADD TRANSACTION
# ═══════════════════════════════════════════════════════════════
def add_transaction_page():
    st.title("➕ নতুন লেনদেন যোগ করুন")
    
    with st.form("tx_form"):
        tx_date = st.date_input("তারিখ", value=date.today())
        name = st.text_input("গ্রাহকের নাম")
        reference = st.text_input("রেফারেন্স")
        service_name = st.text_input("সেবার নাম/কাজের ধরন")
        
        payment = st.number_input("আপনার নিজের খরচ/ক্রয়মূল্য", min_value=0, value=0)
        amount = st.number_input("গ্রাহকের মোট বিল", min_value=0, value=0)
        received = st.number_input("গ্রাহক থেকে নগদ আদায়", min_value=0, value=0)
        
        status = st.selectbox("স্ট্যাটাস", [("R", "পেইড"), ("P", "বাকি"), ("A", "অগ্রিম")], format_func=lambda x: x[1])
        notes = st.text_area("নোট (ঐচ্ছিক)")
        
        submitted = st.form_submit_button("💾 লাইভ সেভ করুন", use_container_width=True)
        if submitted:
            if not service_name:
                st.error("সেবার নাম দিন")
            else:
                save_transaction({
                    "transaction_date": tx_date.isoformat(),
                    "customer_name": name,
                    "service_type_name": service_name,
                    "amount": int(amount),
                    "payment": int(payment),
                    "received_amount": int(received),
                    "status": status[0],
                    "reference": reference,
                    "notes": notes,
                })
                st.success("লেনদেন সরাসরি গুগল শিটে সেভ হয়েছে!")
                st.balloons()
                
    if st.button("← ড্যাশবোর্ডে ফিরুন", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()

# ═══════════════════════════════════════════════════════════════
# TRANSACTION HISTORY
# ═══════════════════════════════════════════════════════════════
def history_page():
    st.title("📋 লেনদেনের লাইভ তালিকা")
    
    df = get_all_transactions()
    
    if df.empty:
        st.warning("কোনো লেনদেন পাওয়া যায়নি")
    else:
        # ডাটা টেবিল আকারে শো করা
        st.dataframe(
            df[["transaction_date", "customer_name", "service_type_name", "amount", "received_amount", "status", "reference"]],
            use_container_width=True,
            column_config={
                "transaction_date": "তারিখ",
                "customer_name": "গ্রাহকের নাম",
                "service_type_name": "সেবা",
                "amount": "মোট বিল",
                "received_amount": "আদায়কৃত",
                "status": "স্ট্যাটাস",
                "reference": "রেফারেন্স"
            },
            hide_index=True
        )
                        
    if st.button("← ড্যাশবোর্ডে ফিরুন", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()

# ── MAIN NAV ───────────────────────────────────────────────────
def main():
    with st.sidebar:
        st.title("📋 দোকানের লাইভ হিসাব")
        st.info("আপনার সব ডেটা সরাসরি Google Sheet-এ লাইভ সেভ হচ্ছে।")
        st.divider()
        if st.button("📊 ড্যাশবোর্ড", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()
        if st.button("➕ লেনদেন যোগ", use_container_width=True):
            st.session_state.page = "add"
            st.rerun()
        if st.button("📋 লেনদেন তালিকা", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()
            
    page = st.session_state.page
    if page == "dashboard":
        dashboard_page()
    elif page == "add":
        add_transaction_page()
    elif page == "history":
        history_page()

if __name__ == "__main__":
    main()
