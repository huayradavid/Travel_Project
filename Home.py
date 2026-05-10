import streamlit as st
import sqlite3
import json
import hashlib
from datetime import datetime

st.set_page_config(page_title="ChicTrip - 會員登入", layout="wide")

# 隱藏預設的側邊欄導覽
st.markdown("""
    <style>[data-testid="stSidebarNav"] {display: none;}</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 資安模組：密碼雜湊加密 (SHA-256)
# ==========================================
def hash_password(password):
    # 將密碼轉換為 SHA-256 雜湊值，避免明文儲存
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_password(password, hashed_password):
    # 驗證使用者輸入的密碼是否與資料庫中的雜湊值相符
    return hash_password(password) == hashed_password

# ==========================================
# 1. 資料庫初始化
# ==========================================
def init_db():
    conn = sqlite3.connect('chictrip.db')
    c = conn.cursor()
    # 新增了 password 欄位
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            join_date TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS itineraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            title TEXT,
            city TEXT,
            created_at TEXT,
            data_json TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 初始化 Session State
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = ""

st.title("🏕️ ChicTrip 智能旅遊平台")

# ==========================================
# 2. 存取控制：如果尚未登入，顯示登入/註冊畫面
# ==========================================
if not st.session_state.logged_in:
    # 使用 Tabs 讓介面更像真實 App
    tab_login, tab_register = st.tabs(["🔑 會員登入", "📝 註冊新帳號"])
    
    with tab_login:
        st.subheader("歡迎回來")
        with st.form("login_form"):
            login_user = st.text_input("帳號 (使用者名稱)")
            login_pass = st.text_input("密碼", type="password") # 隱藏密碼輸入
            submit_login = st.form_submit_button("登入", type="primary", use_container_width=True)
            
            if submit_login:
                conn = sqlite3.connect('chictrip.db')
                c = conn.cursor()
                c.execute("SELECT password FROM users WHERE username=?", (login_user,))
                result = c.fetchone()
                conn.close()
                
                if result and check_password(login_pass, result[0]):
                    st.session_state.logged_in = True
                    st.session_state.current_user = login_user
                    st.success("✅ 登入成功！正在為您轉跳...")
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 帳號或密碼錯誤，請重新輸入。")

    with tab_register:
        st.subheader("建立新帳號")
        with st.form("register_form"):
            new_user = st.text_input("設定帳號 (使用者名稱)")
            new_pass = st.text_input("設定密碼", type="password")
            new_pass_confirm = st.text_input("確認密碼", type="password")
            submit_register = st.form_submit_button("註冊", use_container_width=True)
            
            if submit_register:
                if new_pass != new_pass_confirm:
                    st.warning("⚠️ 兩次輸入的密碼不一致！")
                elif not new_user or not new_pass:
                    st.warning("⚠️ 帳號與密碼不能為空！")
                else:
                    try:
                        conn = sqlite3.connect('chictrip.db')
                        c = conn.cursor()
                        # 存入資料庫的是「雜湊過」的密碼，不是明文！
                        c.execute("INSERT INTO users (username, password, join_date) VALUES (?, ?, ?)", 
                                  (new_user, hash_password(new_pass), datetime.now().strftime("%Y-%m-%d %H:%M")))
                        conn.commit()
                        conn.close()
                        st.success("✅ 註冊成功！請切換到「會員登入」頁籤進行登入。")
                    except sqlite3.IntegrityError:
                        st.error("❌ 此帳號已被註冊過了喔！")

# ==========================================
# 3. 儀表板：登入後才會顯示的內容
# ==========================================
else:
    # 頂部歡迎列與登出按鈕
    col_welcome, col_logout = st.columns([4, 1])
    with col_welcome:
        st.write(f"👋 歡迎回來，**{st.session_state.current_user}**！這是你的專屬旅遊儀表板。")
    with col_logout:
        if st.button("🚪 登出", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.current_user = ""
            st.rerun()
            
    st.divider()

    # 以下是原本的儀表板邏輯 (建立行程與歷史行程)
    col_new, col_history = st.columns([1, 2])

    with col_new:
        st.subheader("✨ 建立新行程")
        with st.container(border=True):
            new_title = st.text_input("行程名稱", placeholder="例如：台南三天兩夜爆吃之旅")
            new_city = st.text_input("主要目的地", placeholder="例如：台南市")
            
            if st.button("➕ 開始規劃", type="primary", use_container_width=True):
                if new_title and new_city:
                    conn = sqlite3.connect('chictrip.db')
                    c = conn.cursor()
                    c.execute("INSERT INTO itineraries (user_id, title, city, created_at, data_json) VALUES (?, ?, ?, ?, ?)",
                              (st.session_state.current_user, new_title, new_city, datetime.now().strftime("%Y-%m-%d %H:%M"), "[]"))
                    new_id = c.lastrowid
                    conn.commit()
                    conn.close()
                    
                    st.session_state.current_trip_id = new_id
                    st.session_state.explore_city = new_city
                    st.session_state.my_itinerary = []
                    st.switch_page("pages/1_行程編輯器.py")
                else:
                    st.warning("請填寫行程名稱與目的地喔！")

    with col_history:
        st.subheader("📚 我的歷史行程")
        
        conn = sqlite3.connect('chictrip.db')
        c = conn.cursor()
        c.execute("SELECT id, title, city, created_at, data_json FROM itineraries WHERE user_id=? ORDER BY id DESC", (st.session_state.current_user,))
        saved_trips = c.fetchall()
        conn.close()
        
        if not saved_trips:
            st.info("目前還沒有儲存的行程，趕快從左邊建立一個吧！")
        else:
            for trip in saved_trips:
                trip_id, title, city, created_at, data_json = trip
                spot_count = len(json.loads(data_json))
                
                with st.container(border=True):
                    c_info, c_btn1, c_btn2 = st.columns([3, 1, 1])
                    with c_info:
                        st.markdown(f"**📍 {title}** ({city})")
                        st.caption(f"🕒 建立於 {created_at} | 包含 {spot_count} 個景點")
                    
                    with c_btn1:
                        if st.button("✏️ 編輯", key=f"edit_{trip_id}", use_container_width=True):
                            st.session_state.current_trip_id = trip_id
                            st.session_state.explore_city = city
                            st.session_state.my_itinerary = json.loads(data_json)
                            st.switch_page("pages/1_行程編輯器.py")
                    with c_btn2:
                        if st.button("🗑️ 刪除", key=f"del_{trip_id}", use_container_width=True):
                            conn = sqlite3.connect('chictrip.db')
                            c = conn.cursor()
                            c.execute("DELETE FROM itineraries WHERE id=?", (trip_id,))
                            conn.commit()
                            conn.close()
                            st.rerun()