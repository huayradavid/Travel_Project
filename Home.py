import streamlit as st
import sqlite3
import json
from datetime import datetime

st.set_page_config(page_title="首頁 - 會員中心", layout="wide")

# --- 隱藏 Streamlit 預設的側邊欄選單 ---
st.markdown("""
    <style>
        /* 隱藏側邊欄的頁面導覽選單 */
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)




# ==========================================
# 1. 資料庫初始化 (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect('chictrip.db')
    c = conn.cursor()
    # 建立行程資料表 (關聯式資料庫設計)
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




# ==========================================
# 2. 模擬會員登入系統
# ==========================================
st.title("🏕️ 智能旅遊平台")

# 簡單的會員切換機制 (實務上這裡會是帳號密碼登入)
users = ["劉鴻勳", "楊譯翔", "張綵倪", "高暐勳"]
current_user = st.selectbox("切換使用者 (模擬登入)", users)
st.session_state.current_user = current_user

st.write(f"👋 歡迎回來，**{current_user}**！這是你的專屬旅遊儀表板。")
st.divider()




# ==========================================
# 3. 儀表板：建立新行程 & 讀取歷史行程
# ==========================================
col_new, col_history = st.columns([1, 2])

with col_new:
    st.subheader("✨ 建立新行程")
    with st.container(border=True):
        new_title = st.text_input("行程名稱", placeholder="例如：台南三天兩夜爆吃之旅")
        new_city = st.text_input("主要目的地", placeholder="例如：台南市")
        
        if st.button("➕ 開始規劃", type="primary", use_container_width=True):
            if new_title and new_city:
                # 在資料庫建立一筆空行程
                conn = sqlite3.connect('chictrip.db')
                c = conn.cursor()
                c.execute("INSERT INTO itineraries (user_id, title, city, created_at, data_json) VALUES (?, ?, ?, ?, ?)",
                          (current_user, new_title, new_city, datetime.now().strftime("%Y-%m-%d %H:%M"), "[]"))
                new_id = c.lastrowid
                conn.commit()
                conn.close()
                
                # 設定 Session State 告訴編輯器我們要編輯哪一筆
                st.session_state.current_trip_id = new_id
                st.session_state.explore_city = new_city
                st.session_state.my_itinerary = [] # 清空畫面
                
                # 跳轉到編輯頁面
                st.switch_page("pages/1_行程編輯器.py")
            else:
                st.warning("請填寫行程名稱與目的地喔！")

with col_history:
    st.subheader("📚 我的歷史行程")
    
    # 從資料庫撈取該會員的所有行程
    conn = sqlite3.connect('chictrip.db')
    c = conn.cursor()
    c.execute("SELECT id, title, city, created_at, data_json FROM itineraries WHERE user_id=? ORDER BY id DESC", (current_user,))
    saved_trips = c.fetchall()
    conn.close()
    
    if not saved_trips:
        st.info("目前還沒有儲存的行程，趕快從左邊建立一個吧！")
    else:
        # 用網格系統展示行程卡片
        for trip in saved_trips:
            trip_id, title, city, created_at, data_json = trip
            
            # 解析 JSON 看看裡面有幾個景點
            itinerary_data = json.loads(data_json)
            spot_count = len(itinerary_data)
            
            with st.container(border=True):
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    st.markdown(f"### 📍 {title}")
                    st.caption(f"目的地：{city} | 建立時間：{created_at} | 包含 {spot_count} 個景點")
                
                with col_btn:
                    # 點擊按鈕載入該行程
                    if st.button("✏️ 繼續編輯", key=f"edit_{trip_id}", use_container_width=True):
                        st.session_state.current_trip_id = trip_id
                        st.session_state.explore_city = city
                        st.session_state.my_itinerary = itinerary_data # 把資料庫的資料塞回編輯器
                        st.switch_page("pages/1_行程編輯器.py")
                    
                    # 刪除行程按鈕
                    if st.button("🗑️ 刪除", key=f"del_{trip_id}", use_container_width=True):
                        conn = sqlite3.connect('chictrip.db')
                        c = conn.cursor()
                        c.execute("DELETE FROM itineraries WHERE id=?", (trip_id,))
                        conn.commit()
                        conn.close()
                        st.rerun()