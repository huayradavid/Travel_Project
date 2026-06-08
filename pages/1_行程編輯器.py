import streamlit as st
import os
import googlemaps
import folium
from streamlit_folium import st_folium
import polyline
import uuid
import time
import math
from datetime import datetime, time as dt_time, timedelta 
import urllib.parse
from dotenv import load_dotenv




# ==========================================
# 🛡️ 路由守衛 (Route Guard)：檢查是否合法進入
# ==========================================
# 如果 Session 裡面沒有 current_trip_id，代表他不是從首頁按按鈕過來的
if 'current_trip_id' not in st.session_state:
    if os.getenv("CHICTRIP_DEMO") == "1":
        st.session_state.current_trip_id = "demo-trip"
        st.session_state.my_itinerary = {
            "第 1 天": [
                {
                    "名稱": "彰化火車站",
                    "地址": "彰化縣彰化市三民路1號",
                    "lat": 24.0815,
                    "lng": 120.5385,
                    "rating": "N/A",
                    "itinerary_id": "demo-1",
                    "transport_mode": "walking",
                    "arr_h": 9,
                    "arr_m": 0,
                    "stay_h": 0,
                    "stay_m": 30,
                    "budget": 0,
                },
                {
                    "名稱": "八卦山大佛風景區",
                    "地址": "彰化縣彰化市溫泉路31號",
                    "lat": 24.0786,
                    "lng": 120.5492,
                    "rating": "N/A",
                    "itinerary_id": "demo-2",
                    "transport_mode": "walking",
                    "stay_h": 1,
                    "stay_m": 0,
                    "budget": 0,
                },
                {
                    "名稱": "彰化孔子廟",
                    "地址": "彰化縣彰化市孔門路30號",
                    "lat": 24.0779,
                    "lng": 120.5424,
                    "rating": "N/A",
                    "itinerary_id": "demo-3",
                    "transport_mode": "walking",
                    "stay_h": 0,
                    "stay_m": 45,
                    "budget": 0,
                },
            ]
        }
        st.session_state.current_day = "第 1 天"
    else:
        st.warning("⚠️ 系統偵測到異常存取！請先從首頁「選擇」或「建立」一個行程。")
        import time
        time.sleep(2) # 停頓 2 秒讓使用者看到警告
        st.switch_page("Home.py") # 強制把他踢回首頁！
        st.stop() # 停止執行後面的程式碼



# ==========================================
# 🔄 狀態初始化與資料相容性處理 (必須在排版前執行)
# ==========================================
# 1. 向下相容：如果資料庫抓出來的是舊版 List，自動升級成 Dict
if isinstance(st.session_state.my_itinerary, list):
    st.session_state.my_itinerary = {"第 1 天": st.session_state.my_itinerary}

# 防呆：如果是全新建立的空行程，給它預設的第 1 天
if not st.session_state.my_itinerary:
    st.session_state.my_itinerary = {"第 1 天": []}

# 2. 確保 current_day 一定存在
days = list(st.session_state.my_itinerary.keys())
if 'current_day' not in st.session_state or st.session_state.current_day not in days:
    st.session_state.current_day = days[0]


# ==========================================
# 🌐 系統語系初始化 (i18n Init)
# ==========================================
if 'app_lang' not in st.session_state:
    st.session_state.app_lang = 'zh' # 預設繁體中文

# 定義語言對照表
lang_mapping = {"繁體中文": "zh", "English": "en"}


# --- 1. 初始化與 API 設定 ---
load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=API_KEY) if API_KEY else None

st.set_page_config(page_title="智能旅遊筆記", layout="wide")

def inject_custom_css():
    st.markdown(
        """
        <style>
        :root {
            --ct-accent: #ff385c;
            --ct-accent-hover: #e31c5f;
            --ct-border: rgba(128, 128, 128, 0.26);
            --ct-border-soft: rgba(128, 128, 128, 0.16);
            --ct-shadow: 0 14px 34px rgba(0, 0, 0, 0.10);
            --ct-radius: 14px;
        }

        .stApp {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
        }

        [data-testid="stAppViewContainer"] > .main .block-container {
            padding-top: 1.35rem;
            padding-left: 2rem;
            padding-right: 2rem;
            max-width: 1480px;
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid var(--ct-border-soft);
        }

        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.75rem;
        }

        .ct-hero {
            background: var(--secondary-background-color);
            color: var(--text-color);
            border: 1px solid var(--ct-border-soft);
            border-radius: 18px;
            box-shadow: var(--ct-shadow);
            padding: 22px 26px;
            margin-bottom: 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
        }

        .ct-hero h1 {
            color: var(--text-color);
            font-size: 30px;
            line-height: 1.15;
            margin: 0 0 7px 0;
            letter-spacing: 0;
        }

        .ct-hero p {
            color: var(--text-color);
            opacity: 0.72;
            font-size: 15px;
            line-height: 1.5;
            margin: 0;
        }

        .ct-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: flex-end;
        }

        .ct-pill {
            display: inline-flex;
            align-items: center;
            min-height: 30px;
            border: 1px solid var(--ct-border);
            border-radius: 999px;
            padding: 6px 10px;
            color: var(--text-color);
            background: var(--background-color);
            font-size: 12px;
            white-space: nowrap;
        }

        .ct-arrival {
            color: var(--text-color);
            font-size: 18px;
            font-weight: 800;
            margin-bottom: 5px;
        }

        .ct-manual-badge {
            font-size: 12px;
            color: var(--ct-accent);
            background: rgba(255, 56, 92, 0.12);
            border: 1px solid rgba(255, 56, 92, 0.28);
            padding: 2px 6px;
            border-radius: 4px;
        }

        h1, h2, h3,
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
            letter-spacing: 0;
        }

        .stMarkdown h2, .stMarkdown h3 {
            margin-top: 0.2rem;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--ct-border-soft) !important;
            border-radius: var(--ct-radius) !important;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
        }

        [data-testid="stForm"] {
            border: 1px solid var(--ct-border-soft);
            border-radius: var(--ct-radius);
            background: var(--secondary-background-color);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
            padding: 14px;
        }

        [data-testid="stTabs"] button {
            border-radius: 999px;
            min-height: 38px;
        }

        [data-testid="stTabs"] button[aria-selected="true"] {
            font-weight: 700;
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button,
        div[data-testid="stFormSubmitButton"] > button,
        a[data-testid="stLinkButton"] {
            border-radius: 999px !important;
            border: 1px solid var(--ct-border) !important;
            font-weight: 700 !important;
            min-height: 40px;
            transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease, background-color 140ms ease;
        }

        div[data-testid="stButton"] > button:hover,
        div[data-testid="stDownloadButton"] > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover,
        a[data-testid="stLinkButton"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 22px rgba(0, 0, 0, 0.16);
            border-color: var(--ct-accent) !important;
        }

        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button[kind="primary"],
        div[data-testid="stDownloadButton"] > button[kind="primary"] {
            background: var(--ct-accent) !important;
            border-color: var(--ct-accent) !important;
            color: #fff !important;
        }

        div[data-testid="stButton"] > button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover,
        div[data-testid="stDownloadButton"] > button[kind="primary"]:hover {
            background: var(--ct-accent-hover) !important;
            border-color: var(--ct-accent-hover) !important;
        }

        [data-testid="stMetric"] {
            background: var(--secondary-background-color);
            border: 1px solid var(--ct-border-soft);
            border-radius: 12px;
            padding: 12px 14px;
        }

        [data-testid="stMetricValue"] {
            font-size: 22px;
        }

        .stAlert {
            border-radius: 12px;
            border: 1px solid var(--ct-border-soft);
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--ct-border-soft);
            border-radius: 12px;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stDateInput"] input,
        textarea {
            border-radius: 10px !important;
            border-color: var(--ct-border) !important;
        }

        [data-testid="stTextInput"] input:focus,
        [data-testid="stNumberInput"] input:focus,
        [data-testid="stDateInput"] input:focus,
        textarea:focus {
            border-color: var(--ct-accent) !important;
            box-shadow: 0 0 0 3px rgba(255, 56, 92, 0.14) !important;
        }

        .folium-map {
            border-radius: 16px;
            overflow: hidden;
        }

        hr {
            border-color: var(--ct-border-soft) !important;
            opacity: 1;
        }

        @media (max-width: 900px) {
            [data-testid="stAppViewContainer"] > .main .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .ct-hero {
                align-items: flex-start;
                flex-direction: column;
            }

            .ct-pill-row {
                justify-content: flex-start;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

inject_custom_css()

# 👉 新增：自動儲存函數
def auto_save_itinerary():
    import sqlite3
    import json
    trip_id = st.session_state.get('current_trip_id')
    if not trip_id:
        return False
    if os.getenv("CHICTRIP_DEMO") == "1" or trip_id == "demo-trip":
        st.session_state["demo_saved_itinerary"] = st.session_state.my_itinerary
        return True

    iti_json = json.dumps(st.session_state.my_itinerary, ensure_ascii=False)
    try:
        conn = sqlite3.connect('chictrip.db')
        c = conn.cursor()
        c.execute("UPDATE itineraries SET data_json=? WHERE id=?", (iti_json, trip_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        st.warning(f"目前無法寫入資料庫，行程仍保留在本次瀏覽器工作階段。原因：{e}")
        return False

def make_place_item(name, address, lat, lng, rating="N/A", transport_mode="driving", stay_h=1, stay_m=0, budget=0):
    return {
        '名稱': name,
        '地址': address,
        'lat': float(lat),
        'lng': float(lng),
        'rating': rating,
        'itinerary_id': str(uuid.uuid4()),
        'transport_mode': transport_mode,
        'stay_h': stay_h,
        'stay_m': stay_m,
        'budget': budget,
    }

def add_place_to_current_day(place):
    current = st.session_state.current_day
    st.session_state.my_itinerary[current].append(place)
    st.session_state.current_directions = build_offline_legs(st.session_state.my_itinerary[current])
    auto_save_itinerary()

def format_minutes(total_minutes):
    total_minutes = int(round(total_minutes))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} 小時 {minutes} 分鐘"
    if hours:
        return f"{hours} 小時"
    return f"{minutes} 分鐘"

def haversine_km(lat1, lng1, lat2, lng2):
    radius = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def estimate_leg(prev_place, next_place):
    mode = next_place.get('transport_mode', 'driving')
    profiles = {
        "driving": {"speed": 35, "factor": 1.25, "cost_per_km": 8, "base_cost": 0},
        "walking": {"speed": 4.5, "factor": 1.15, "cost_per_km": 0, "base_cost": 0},
        "transit": {"speed": 22, "factor": 1.35, "cost_per_km": 2.5, "base_cost": 20},
        "bicycling": {"speed": 12, "factor": 1.2, "cost_per_km": 0, "base_cost": 0},
    }
    profile = profiles.get(mode, profiles["driving"])
    distance_km = haversine_km(
        prev_place.get('lat', 24.08),
        prev_place.get('lng', 120.54),
        next_place.get('lat', 24.08),
        next_place.get('lng', 120.54),
    ) * profile["factor"]
    minutes = max(3, distance_km / profile["speed"] * 60)
    cost = profile["base_cost"] + distance_km * profile["cost_per_km"]
    return {
        "duration": {"value": int(minutes * 60), "text": format_minutes(minutes)},
        "distance": {"value": int(distance_km * 1000), "text": f"{distance_km:.1f} 公里"},
        "offline_estimate": True,
        "mode": mode,
        "cost": round(cost),
    }

def build_offline_legs(itinerary):
    return [estimate_leg(itinerary[i], itinerary[i + 1]) for i in range(len(itinerary) - 1)]

def summarize_day(itinerary, legs):
    stay_minutes = sum(p.get('stay_h', 1) * 60 + p.get('stay_m', 0) for p in itinerary)
    travel_minutes = sum(leg['duration']['value'] / 60 for leg in legs)
    distance_km = sum(leg['distance']['value'] / 1000 for leg in legs)
    transport_cost = sum(leg.get('cost', 0) for leg in legs)
    place_cost = sum(int(p.get('budget', 0) or 0) for p in itinerary)
    total_minutes = stay_minutes + travel_minutes
    return {
        "stay_minutes": stay_minutes,
        "travel_minutes": travel_minutes,
        "distance_km": distance_km,
        "transport_cost": transport_cost,
        "place_cost": place_cost,
        "total_cost": transport_cost + place_cost,
        "total_minutes": total_minutes,
    }

def local_route_order(itinerary):
    if len(itinerary) < 3:
        return itinerary
    start, end = itinerary[0], itinerary[-1]
    remaining = itinerary[1:-1]
    ordered = [start]
    current = start
    while remaining:
        next_place = min(
            remaining,
            key=lambda p: haversine_km(current.get('lat', 24.08), current.get('lng', 120.54), p.get('lat', 24.08), p.get('lng', 120.54))
        )
        ordered.append(next_place)
        remaining.remove(next_place)
        current = next_place
    ordered.append(end)
    return ordered

def build_day_schedule(itinerary, base_date, legs=None):
    legs = legs if legs is not None else build_offline_legs(itinerary)
    rows = []
    current_dt = datetime.combine(base_date, dt_time(itinerary[0].get('arr_h', 8), itinerary[0].get('arr_m', 0))) if itinerary else None
    for i, place in enumerate(itinerary):
        if i > 0:
            prev = itinerary[i - 1]
            current_dt += timedelta(hours=prev.get('stay_h', 1), minutes=prev.get('stay_m', 0))
            current_dt += timedelta(seconds=legs[i - 1]['duration']['value'])
            if place.get('use_manual_arr', False):
                current_dt = datetime.combine(base_date, dt_time(place.get('arr_h', 8), place.get('arr_m', 0)))
        end_dt = current_dt + timedelta(hours=place.get('stay_h', 1), minutes=place.get('stay_m', 0))
        rows.append({"place": place, "start": current_dt, "end": end_dt})
    return rows

def make_ics(my_itinerary, start_date):
    def esc(text):
        return str(text).replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ChicTrip//Travel Planner//ZH-TW"]
    for day_index, (day_name, day_iti) in enumerate(my_itinerary.items()):
        if not day_iti:
            continue
        day_date = start_date + timedelta(days=day_index)
        for row in build_day_schedule(day_iti, day_date):
            place = row["place"]
            uid = place.get('itinerary_id', str(uuid.uuid4()))
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}@chictrip.local",
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{row['start'].strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{row['end'].strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{esc(place.get('名稱', '旅遊景點'))}",
                f"LOCATION:{esc(place.get('地址', ''))}",
                f"DESCRIPTION:{esc(day_name + ' - ChicTrip 行程')}",
                "END:VEVENT",
            ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode("utf-8")

# --- 2. 初始化 Session State ---
if 'next_page_token' not in st.session_state:
    st.session_state.next_page_token = None
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'my_itinerary' not in st.session_state:
    st.session_state.my_itinerary = []
if 'picked_lat' not in st.session_state:
    st.session_state.picked_lat = 24.0868
if 'picked_lng' not in st.session_state:
    st.session_state.picked_lng = 120.5387

st.markdown(
    """
    <section class="ct-hero">
        <div>
            <h1>ChicTrip 智能旅遊規劃</h1>
            <p>把景點、路線、時間、預算與匯出整理在同一個工作台。測試模式可用本機估算，不需要 Google API。</p>
        </div>
        <div class="ct-pill-row">
            <span class="ct-pill">OpenStreetMap 預覽</span>
            <span class="ct-pill">本機順路排序</span>
            <span class="ct-pill">PDF / ICS 匯出</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

# --- 2. 建立三欄式版面 ---
col_search, col_map, col_plan = st.columns([1, 1.8, 1.2]) # 調整比例讓地圖大一點

# ==========================================
# 💾 側邊控制面板 (多日行程升級版)
# ==========================================
with st.sidebar:
    
    st.subheader("⚙️ 行程控制台")
    trip_id = st.session_state.get('current_trip_id', '未知')
    st.caption(f"目前編輯行程 ID：{trip_id}")

    # 👉 核心技術 1：資料結構遷移 (List 轉 Dict)
    # 檢查如果資料庫讀出來的是舊版的 list，自動幫它包裝成 "第 1 天"
    if isinstance(st.session_state.my_itinerary, list):
        st.session_state.my_itinerary = {"第 1 天": st.session_state.my_itinerary}
        
    st.divider()

    st.toggle("省 API 模式（本機估算路線）", value=True, key="low_api_mode")
    if st.session_state.low_api_mode:
        st.caption("目前使用 OpenStreetMap 底圖與直線距離估算，不會呼叫 Google Directions。")
    elif not gmaps:
        st.warning("尚未設定 GOOGLE_MAPS_API_KEY，已無法使用 Google 搜尋與真實路線。")
    
    if st.button("💾 手動儲存", use_container_width=True):
        saved = auto_save_itinerary()
        if os.getenv("CHICTRIP_DEMO") == "1" or trip_id == "demo-trip":
            st.success("✅ Demo 行程已暫存在目前工作階段。")
        elif saved:
            st.success("✅ 行程已成功儲存！")
    if st.button("⬅️ 回到會員首頁", use_container_width=True):
        st.switch_page("Home.py")

# ==========================================
# 📖 多國語系字典 (i18n Dictionary)
# ==========================================
i18n = {
    "zh": {
        "sidebar_title": "⚙️ 行程控制台",
        "save_btn": "💾 手動儲存",
        "home_btn": "⬅️ 回到會員首頁",
        "my_plan": "📅 我的行程表",
        "add_day": "➕ 新增一天",
        "add_place": "➕ 加入行程",
        "ai_sort": "✨ 讓 AI 幫我重新順路排序"
    },
    "en": {
        "sidebar_title": "⚙️ Console",
        "save_btn": "💾 Save",
        "home_btn": "⬅️ Back to Home",
        "my_plan": "📅 My Itinerary",
        "add_day": "➕ Add Day",
        "add_place": "➕ Add Place",
        "ai_sort": "✨ AI Route Optimization"
    }
}

# 取得現在的語言，方便下面呼叫
lang = st.session_state.app_lang
api_lang = 'zh-TW' if lang == 'zh' else 'en'

# ==========================================
# 📍 左欄：尋找景點 (包含圖文、分頁、雙軌搜尋)
# ==========================================
with col_search:
    st.subheader("🔍 尋找景點")
    # 👉 插入這行：建立一個高度 750px 的獨立滾動視窗
    with st.container(height=750, border=False):
        if not gmaps:
            st.info("目前沒有設定 GOOGLE_MAPS_API_KEY，因此搜尋改用手動新增模式；路線、排序、預算、PDF、ICS 仍可測試。")
            st.caption(f"🖱️ 可直接點擊中間地圖選位置，目前座標：{st.session_state.picked_lat:.6f}, {st.session_state.picked_lng:.6f}")
            with st.form("manual_place_form", clear_on_submit=True):
                st.write("✍️ **手動新增景點**")
                manual_name = st.text_input("景點名稱", value="彰化扇形車庫")
                manual_address = st.text_input("地址或備註", value="彰化縣彰化市彰美路一段1號")
                col_lat, col_lng = st.columns(2)
                with col_lat:
                    manual_lat = st.number_input("緯度", value=float(st.session_state.picked_lat), format="%.6f")
                with col_lng:
                    manual_lng = st.number_input("經度", value=float(st.session_state.picked_lng), format="%.6f")
                col_stay_h, col_stay_m = st.columns(2)
                with col_stay_h:
                    manual_stay_h = st.number_input("停留小時", min_value=0, max_value=24, value=1)
                with col_stay_m:
                    manual_stay_m = st.number_input("停留分鐘", min_value=0, max_value=59, value=0)
                manual_budget = st.number_input("預估花費（TWD）", min_value=0, value=0, step=50)
                submitted = st.form_submit_button("➕ 加入手動景點", use_container_width=True)
                if submitted:
                    add_place_to_current_day(make_place_item(
                        manual_name,
                        manual_address,
                        manual_lat,
                        manual_lng,
                        stay_h=manual_stay_h,
                        stay_m=manual_stay_m,
                        budget=manual_budget,
                    ))
                    st.toast(f"✅ 已加入 {manual_name}")
                    st.rerun()

            if st.button("📌 載入更多彰化範例景點", use_container_width=True):
                demo_places = [
                    make_place_item("彰化扇形車庫", "彰化縣彰化市彰美路一段1號", 24.0868, 120.5387, stay_h=1),
                    make_place_item("鹿港老街", "彰化縣鹿港鎮瑤林街", 24.0567, 120.4318, transport_mode="driving", stay_h=2, budget=300),
                    make_place_item("鹿港天后宮", "彰化縣鹿港鎮中山路430號", 24.0581, 120.4331, transport_mode="walking", stay_h=1),
                ]
                for demo_place in demo_places:
                    add_place_to_current_day(demo_place)
                st.toast("✅ 已載入範例景點")
                st.rerun()

            st.divider()

        tab_explore, tab_search = st.tabs(["💡 探索推薦", "🎯 精準搜尋"])
        # --- 標籤 1：探索推薦 ---
        with tab_explore:
            explore_city = st.text_input("你想探索哪個區域？", value="彰化市", key="explore_city")
        
            # 建立完整的 Google Places API 類型對應表 (加上 Emoji 提升質感)
            poi_mapping = {
                "tourist_attraction": "📸 旅遊景點",
                "restaurant": "🍽️ 美食餐廳",
                "cafe": "☕ 咖啡廳",
                "lodging": "🏨 住宿與飯店",
                "shopping_mall": "🛍️ 購物中心與商圈",
                "museum": "🏛️ 博物館與展覽",
                "park": "🌳 公園與自然生態",
                "amusement_park": "🎢 主題遊樂園",
                "bakery": "🥐 甜點與伴手禮",
                "bar": "🍻 酒吧與夜生活",
                "convenience_store": "🏪 便利商店"
            }
            
            # 將字典的 key 取出作為選單選項，並用 format_func 顯示漂亮的中文
            poi_type = st.selectbox("尋找特定類型", list(poi_mapping.keys()), 
                                    format_func=lambda x: poi_mapping[x])
            
            radius_km = st.slider("搜尋範圍 (公里)", 1, 30, 5) 
            
            if st.button("在地推薦", type="primary", use_container_width=True):
                if not gmaps:
                    st.warning("尚未設定 GOOGLE_MAPS_API_KEY，請先使用上方的手動新增景點測試。")
                    st.stop()
                with st.spinner("尋找熱門推薦中..."):
                    try:
                        geocode_result = gmaps.geocode(explore_city)
                        if geocode_result:
                            loc = geocode_result[0]['geometry']['location']
                            # 第一次請求
                            res = gmaps.places_nearby(location=loc, radius=radius_km*1000, type=poi_type, language=api_lang)
                            
                            st.session_state.search_results = []
                            for place in res.get('results', []):
                                st.session_state.search_results.append({
                                    '名稱': place.get('name'),
                                    '地址': place.get('vicinity', '無地址'),
                                    '評分': place.get('rating', 0),
                                    'lat': place['geometry']['location']['lat'],
                                    'lng': place['geometry']['location']['lng'],
                                    'place_id': place['place_id']
                                })
                            # 存下分頁 Token
                            st.session_state.next_page_token = res.get('next_page_token')
                    except Exception as e:
                        st.error(f"探索失敗：{e}")

        # --- 標籤 2：精準搜尋 ---
        with tab_search:
            search_query = st.text_input("輸入特定店名或地點", placeholder="例如：彰化火車站", key="search_query")
            if st.button("精準搜尋", use_container_width=True):
                if not gmaps:
                    st.warning("尚未設定 GOOGLE_MAPS_API_KEY，請先使用上方的手動新增景點測試。")
                    st.stop()
                if search_query:
                    with st.spinner("搜尋中..."):
                        try:
                            res = gmaps.places(query=search_query, language=api_lang)
                            st.session_state.search_results = []
                            for place in res.get('results', []):
                                st.session_state.search_results.append({
                                    '名稱': place.get('name'),
                                    '地址': place.get('formatted_address', '無地址'),
                                    '評分': place.get('rating', 0),
                                    'lat': place['geometry']['location']['lat'],
                                    'lng': place['geometry']['location']['lng'],
                                    'place_id': place['place_id']
                                })
                            # Text Search 不處理分頁
                            st.session_state.next_page_token = None 
                        except Exception as e:
                            st.error(f"搜尋失敗：{e}")

        # --- 顯示搜尋結果 (含圖文面板與載入更多) ---
        if st.session_state.search_results:
            st.divider()
            st.write("🎯 **搜尋結果：**")
            
            # 1. 顯示景點卡片
            for i, place in enumerate(st.session_state.search_results):
                with st.container(border=True):
                    st.markdown(f"**{place['名稱']}** (⭐ {place['評分']})")
                    st.caption(f"🏠 {place['地址']}")
                    
                    # 沉浸式圖文展開面板
                    with st.expander("ℹ️ 查看照片與詳細資訊"):
                        try:
                            details = gmaps.place(
                                place_id=place['place_id'],
                                language=api_lang,
                                fields=['formatted_phone_number', 'opening_hours', 'photo', 'review']
                            ).get('result', {})
                            
                            if 'photos' in details and len(details['photos']) > 0:
                                photo_ref = details['photos'][0]['photo_reference']
                                photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={API_KEY}"
                                st.image(photo_url, use_container_width=True)
                                
                            # --- 功能三：MaaS 整合按鈕 ---
                            m1, m2 = st.columns(2)
                            with m1:
                                nav_url = f"https://www.google.com/maps/dir/?api=1&destination={place.get('name')}&destination_place_id={place['place_id']}"
                                st.link_button("🚩 導航", nav_url, use_container_width=True)
                            with m2:
                                uber_url = f"https://m.uber.com/ul/?action=setPickup&dlat={place['geometry']['location']['lat']}&dlng={place['geometry']['location']['lng']}&daddress={place.get('name')}"
                                st.link_button("🚕 Uber", uber_url, use_container_width=True)
                        except: st.caption("載入細節中...")
                    
                    # 加入行程按鈕 (直接使用 place_id 保證全網唯一)
                    if st.button(i18n[lang]["add_place"], key=f"add_{place['place_id']}", type="primary", use_container_width=True):
                        
                        # 🚀 終極殺手鐧：即時資料補水 (Data Hydration)
                        # 直接用 place_id 向 Google 索取最精準的座標！(fields=['geometry'] 可以省 API 費用)
                        if 'lat' in place and 'lng' in place:
                            true_lat = place['lat']
                            true_lng = place['lng']
                        else:
                            try:
                                geo_result = gmaps.place(place_id=place['place_id'], fields=['geometry'])['result']
                                true_lat = geo_result['geometry']['location']['lat']
                                true_lng = geo_result['geometry']['location']['lng']
                            except Exception as e:
                                st.error(f"取得座標失敗，請重試！({e})")
                                st.stop() # 停止往下執行

                        new_item = {
                            '名稱': place['名稱'],
                            '地址': place['地址'],
                            'lat': true_lat,  # 🚀 這次是 100% 純天然的真實座標！
                            'lng': true_lng,  # 🚀 這次是 100% 純天然的真實座標！
                            'rating': place.get('評分', 'N/A'),
                            'itinerary_id': str(uuid.uuid4()),
                            'transport_mode': 'driving' # 預設交通工具
                        }
                        
                        # 取得目前編輯的天數
                        current = st.session_state.current_day
                        st.session_state.my_itinerary[current].append(new_item)
                        
                        # 自動儲存到資料庫
                        auto_save_itinerary()
                        st.toast(f"✅ 已加入 {place['名稱']}")
                        st.rerun()

            # 2. 載入更多按鈕 (如果還有下一頁)
            if st.session_state.next_page_token:
                if st.button("🔽 載入更多熱門景點", use_container_width=True, type="secondary"):
                    if not gmaps:
                        st.warning("尚未設定 GOOGLE_MAPS_API_KEY，請先使用上方的手動新增景點測試。")
                        st.stop()
                    with st.spinner("向 Google 請求更多資料中..."):
                        time.sleep(2) # 必須等待 2 秒否則 API 會報錯
                        try:
                            res = gmaps.places_nearby(page_token=st.session_state.next_page_token)
                            for place in res.get('results', []):
                                st.session_state.search_results.append({
                                    '名稱': place.get('name'),
                                    '地址': place.get('vicinity', '無地址'),
                                    '評分': place.get('rating', 0),
                                    'lat': place['geometry']['location']['lat'],
                                    'lng': place['geometry']['location']['lng'],
                                    'place_id': place['place_id']
                                })
                            st.session_state.next_page_token = res.get('next_page_token')
                            st.rerun()
                        except Exception as e:
                            st.error(f"載入失敗，請稍後再試：{e}")




# ==========================================
# 🗺️ 中欄：實時地圖呈現 (Sprint 2 核心)
# ==========================================
with col_map:
    st.subheader("🗺️ 行程路徑地圖")
        
    # 👉 1. 安全獲取當天行程 (如果找不到，預設給空陣列)
    itinerary = st.session_state.my_itinerary.get(st.session_state.current_day, [])
        
    # 👉 2. 終極防呆機制：確保它是陣列，且裡面至少有一個景點
    if isinstance(itinerary, list) and len(itinerary) > 0:
        first_place = itinerary[0]
        # 使用 .get() 安全取值，如果舊資料沒有 'lat'，預設給彰化市的座標
        lat = first_place.get('lat', 24.08)
        lng = first_place.get('lng', 120.54)
        map_center = [lat, lng]
        zoom_lv = 14
    else:
        map_center = [24.08, 120.54] # 彰化預設座標
        zoom_lv = 13

    # 省 API 模式預設使用 OpenStreetMap，避免地圖瓦片與 Directions 產生 Google API 用量。
    use_google_routes = (not st.session_state.get("low_api_mode", True)) and gmaps
    if use_google_routes:
        google_tiles = f'https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}&key={API_KEY}'
        m = folium.Map(location=map_center, zoom_start=zoom_lv, tiles=google_tiles, attr='Google')
    else:
        m = folium.Map(location=map_center, zoom_start=zoom_lv, tiles="OpenStreetMap")

    if st.session_state.get('picked_lat') is not None and st.session_state.get('picked_lng') is not None:
        folium.Marker(
            [st.session_state.picked_lat, st.session_state.picked_lng],
            popup="待新增位置",
            tooltip="點擊地圖選取的位置",
            icon=folium.Icon(color="red", icon="plus", prefix="fa")
        ).add_to(m)

    if len(itinerary) > 0:
        # 1. 繪製景點標記 (加上防呆取值)
        for i, place in enumerate(itinerary):
            # 👉 安全取值：如果舊資料沒有經緯度或名稱，給予預設值
            lat = place.get('lat', 24.08)
            lng = place.get('lng', 120.54)
            name = place.get('名稱', '未知景點')
            
            folium.Marker(
                [lat, lng],
                popup=f"{i+1}. {name}",
                tooltip=f"第 {i+1} 站",
                icon=folium.DivIcon(html=f"""
                    <div style="
                        font-family: sans-serif; color: white; background-color: #4285F4; 
                        border-radius: 50%; width: 24px; height: 24px; display: flex; 
                        justify-content: center; align-items: center; font-weight: bold; 
                        border: 2px solid white; box-shadow: 0px 2px 4px rgba(0,0,0,0.3);
                    ">{i+1}</div>""")
            ).add_to(m)

        # 2. 繪製真實道路連線 (逐段計算以反應不同交通工具，並加上防呆)
        if len(itinerary) >= 2:
            try:
                all_legs_info = [] # 存每一段的時間
                route_points = []
                
                for k in range(len(itinerary) - 1):
                    # 安全取值：交通方式與前後點座標
                    mode = itinerary[k+1].get('transport_mode', 'driving')
                    lat1, lng1 = itinerary[k].get('lat', 24.08), itinerary[k].get('lng', 120.54)
                    lat2, lng2 = itinerary[k+1].get('lat', 24.08), itinerary[k+1].get('lng', 120.54)
                    
                    if use_google_routes:
                        res = gmaps.directions(
                            origin=f"{lat1},{lng1}",
                            destination=f"{lat2},{lng2}",
                            mode=mode,
                            language=api_lang
                        )
                        if res:
                            all_legs_info.append(res[0]['legs'][0])
                            points = polyline.decode(res[0]['overview_polyline']['points'])
                            route_points.extend(points)
                            # 畫出該段路線
                            folium.PolyLine(points, color="#4285F4", weight=5, opacity=0.7).add_to(m)
                    else:
                        leg = estimate_leg(itinerary[k], itinerary[k + 1])
                        all_legs_info.append(leg)
                        folium.PolyLine(
                            [(lat1, lng1), (lat2, lng2)],
                            color="#2E86AB",
                            weight=4,
                            opacity=0.65,
                            dash_array="8, 8",
                            tooltip=f"本機估算：{leg['duration']['text']} / {leg['distance']['text']}"
                        ).add_to(m)
                
                # 存下所有段落的資訊供右欄顯示
                st.session_state.current_directions = all_legs_info
                    
            except Exception as e:
                st.error(f"路徑計算更新中... ({e})")

    # 渲染地圖，並把使用者點擊的位置回填到手動新增表單。
    map_data = st_folium(m, width="100%", height=600, key="v3_main_map")
    clicked = map_data.get("last_clicked") if map_data else None
    if clicked:
        new_lat = round(clicked["lat"], 6)
        new_lng = round(clicked["lng"], 6)
        if new_lat != st.session_state.picked_lat or new_lng != st.session_state.picked_lng:
            st.session_state.picked_lat = new_lat
            st.session_state.picked_lng = new_lng
            st.toast(f"📍 已選取座標：{new_lat}, {new_lng}")
            st.rerun()




# ==========================================
# 📅 右欄：我的行程表 (CRUD 完整邏輯)
# ==========================================
with col_plan:
    st.subheader(i18n[lang]["my_plan"])

    # ==========================================
    # 📅 天數導覽列 (仿 App 橫向標籤列)
    # ==========================================
    days = list(st.session_state.my_itinerary.keys())
    
    # 建立三欄：左邊放橫向天數選單，右邊放 + 和 -
    col_days, col_add, col_del = st.columns([6, 1, 1])
    
    with col_days:
        # 🚀 秘訣：使用 horizontal=True 讓單選按鈕變成橫向排列，模仿頁籤效果
        current_idx = days.index(st.session_state.current_day) if st.session_state.current_day in days else 0
        new_day_choice = st.radio(
            "選擇天數", 
            options=days, 
            index=current_idx, 
            horizontal=True, # 橫向排列
            label_visibility="collapsed", # 隱藏標題
            key="day_selector_top"
        )
        if new_day_choice != st.session_state.current_day:
            st.session_state.current_day = new_day_choice
            st.rerun()

    with col_add:
        if st.button("➕", help="新增一天", use_container_width=True):
            new_day_name = f"第 {len(days) + 1} 天"
            st.session_state.my_itinerary[new_day_name] = []
            st.session_state.current_day = new_day_name
            auto_save_itinerary()
            st.rerun()
            
    with col_del:
        if st.button("➖", help="刪除目前這天", use_container_width=True):
            if len(days) > 1:
                # 刪除當前天數
                del st.session_state.my_itinerary[st.session_state.current_day]
                # 🚀 防呆機制：重新命名剩下的天數 (例如刪掉第2天，原本的第3天要變成第2天)
                new_iti = {}
                for idx, (old_day, places) in enumerate(st.session_state.my_itinerary.items()):
                    new_iti[f"第 {idx + 1} 天"] = places
                st.session_state.my_itinerary = new_iti
                # 切換回第一天
                st.session_state.current_day = list(new_iti.keys())[0]
                auto_save_itinerary()
                st.toast("✅ 天數已刪除並重新排序")
                st.rerun()
            else:
                st.warning("至少要保留一天喔！")
                
    st.divider() # 加一條分隔線

    # 👉 同樣插入這行：為行程表建立獨立滾動視窗
    with st.container(height=750, border=False):
        iti = st.session_state.my_itinerary[st.session_state.current_day]

        if not iti:
            st.info("目前行程空空的，從左側加入景點吧！")
        else:
            import datetime as dt
            today = dt.date.today()
            current_dt = None # 用來記錄不斷往後推算的虛擬時鐘

            # ==========================================
            # 🤖 智能標誌推算引擎 (Smart Icon Engine)
            # 根據景點名稱的關鍵字，自動配對最適合的 Emoji
            # ==========================================
            def get_place_icon(name):
                name = str(name).lower()
                if any(k in name for k in ['飯店', '酒店', '旅館', '民宿', 'hotel', 'resort', '住宿']): return '🏨'
                if any(k in name for k in ['車站', '高鐵', '火車', '捷運', 'station', '站', '轉運']): return '🚆'
                if any(k in name for k in ['機場', '空港', 'airport', '航空']): return '✈️'
                if any(k in name for k in ['餐廳', '食堂', '咖啡', 'cafe', '壽司', '燒肉', '麵', '屋', '冰', '鍋', 'eat']): return '🍽️'
                if any(k in name for k in ['百貨', '商場', 'outlet', '市場', '夜市', '店', 'mall', '超市', '唐吉訶德']): return '🛍️'
                if any(k in name for k in ['寺', '廟', '宮', '神社', '神宮', '大佛', '堂']): return '⛩️'
                if any(k in name for k in ['公園', '山', '海', '島', '湖', '林', 'park', '岬', '灣']): return '🌲'
                if any(k in name for k in ['館', '博物館', '美術館', 'museum', '展覽']): return '🏛️'
                if any(k in name for k in ['樂園', '動物園', '水族館', 'disney', '影城']): return '🎡'
                return '📍' # 如果都沒中，給一個百搭的地標符號

            for i, p in enumerate(iti):
                
                # ==========================================
                # ⏳ 核心運算：動態時間推算引擎
                # ==========================================
                if i == 0:
                    # 第一站：強制使用手動設定的時間 (預設早上 08:00 出發)
                    start_h = p.get('arr_h', 8)
                    start_m = p.get('arr_m', 0)
                    current_dt = dt.datetime.combine(today, dt.time(start_h, start_m))
                else:
                    # 後續站點：先計算「系統推算時間」= 前一站時間 + 停留時間 + 交通時間
                    prev_p = iti[i-1]
                    current_dt += dt.timedelta(hours=prev_p.get('stay_h', 1), minutes=prev_p.get('stay_m', 0))
                    
                    if st.session_state.get('current_directions') and i-1 < len(st.session_state.current_directions):
                        leg = st.session_state.current_directions[i-1]
                        current_dt += dt.timedelta(seconds=leg['duration']['value'])
                    
                    # 🛡️ 防延誤機制：如果使用者有「手動鎖定」這站的時間，就覆蓋系統推算！
                    if p.get('use_manual_arr', False):
                        current_dt = dt.datetime.combine(today, dt.time(p.get('arr_h', 8), p.get('arr_m', 0)))

                # 格式化顯示時間
                arrival_time_str = current_dt.strftime("%H:%M")

                # ==========================================
                # 🚗 交通資訊區塊 (與之前相同)
                # ==========================================
                if i > 0:
                    current_mode = p.get('transport_mode', 'driving')
                    mode_options = {"driving": "🚗 開車", "walking": "🚶 步行", "transit": "🚌 大眾運輸", "bicycling": "🚲 單車"}
                    leg_info = "--"
                    if st.session_state.get('current_directions') and i-1 < len(st.session_state.current_directions):
                        leg = st.session_state.current_directions[i-1]
                        leg_info = f"{leg['duration']['text']} ({leg['distance']['text']})"

                    with st.popover(f"{mode_options.get(current_mode)}：{leg_info} ▾", use_container_width=True):
                        def update_mode(idx, key_name):
                            new_mode = st.session_state[key_name]
                            st.session_state.my_itinerary[st.session_state.current_day][idx]['transport_mode'] = new_mode
                            auto_save_itinerary()

                        radio_key = f"temp_mode_{p['itinerary_id']}"
                        st.radio("更改交通方式：", options=list(mode_options.keys()), format_func=lambda x: mode_options[x],
                                 index=list(mode_options.keys()).index(current_mode), key=radio_key,
                                 on_change=update_mode, kwargs={"idx": i, "key_name": radio_key})
                        st.divider()
                        lat1, lng1 = iti[i-1].get('lat', 24.08), iti[i-1].get('lng', 120.54)
                        lat2, lng2 = p.get('lat', 24.08), p.get('lng', 120.54)
                        nav_url = f"https://www.google.com/maps/dir/?api=1&origin={lat1},{lng1}&destination={lat2},{lng2}&travelmode={current_mode}"
                        st.link_button("🚀 開啟導航", nav_url, use_container_width=True)
                
                # ==========================================
                # 🎯 景點資訊卡片與彈出設定 (完美還原截圖)
                # ==========================================
                with st.container(border=True):
                    # 顯示抵達時間 (如果有手動更改，加上標記)
                    manual_badge = " <span class='ct-manual-badge'>手動更改</span>" if p.get('use_manual_arr') else ""
                    
                    # 🚀 呼叫智能引擎，取得專屬標誌
                    place_icon = get_place_icon(p['名稱'])
                    
                    # 把寫死的 🚆 換成變數 {place_icon}
                    st.markdown(f"<div class='ct-arrival'>{place_icon} {arrival_time_str} 抵達{manual_badge}</div>", unsafe_allow_html=True)
                    
                    place_icon = get_place_icon(p['名稱'])
                    st.markdown(f"**{i+1}. {place_icon} {p['名稱']}**")
                    curr_h, curr_m = p.get('stay_h', 1), p.get('stay_m', 0)
                    st.caption(f"⏳ 停留時間：{curr_h} 小時 {curr_m} 分鐘")
                    
                    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.5])
                    with c1: 
                        if i > 0 and st.button("⬆️", key=f"u_{p['itinerary_id']}"):
                            iti[i-1], iti[i] = iti[i], iti[i-1]; st.rerun()
                    with c2:
                        if i < len(iti)-1 and st.button("⬇️", key=f"d_{p['itinerary_id']}"):
                            iti[i+1], iti[i] = iti[i], iti[i+1]; st.rerun()
                    with c3:
                        if st.button("❌", key=f"x_{p['itinerary_id']}"):
                            iti.pop(i); st.rerun()
                    with c4:
                        # 🚀 完美還原截圖的設定面板
                        with st.popover("⚙️ 設定", use_container_width=True):
                            st.markdown(f"**編輯 {p['名稱']}**")
                            
                            # --- 第一區：抵達時間 (精確雙滾輪升級版) ---
                            st.write("🕒 **抵達時間**")
                            
                            # 預先撈出這站目前儲存的時分 (如果沒有，就用目前系統推算出的 current_dt 的時分)
                            saved_arr_h = p.get('arr_h', current_dt.hour)
                            saved_arr_m = p.get('arr_m', current_dt.minute)
                            
                            if i == 0:
                                st.caption("💡 首站抵達時間即為今日【出發時間】")
                                col_arr_h, col_arr_m = st.columns(2)
                                with col_arr_h:
                                    final_arr_h = st.selectbox("出發 時", options=list(range(24)), index=saved_arr_h, key=f"arr_h_{p['itinerary_id']}")
                                with col_arr_m:
                                    final_arr_m = st.selectbox("出發 分", options=list(range(60)), index=saved_arr_m, key=f"arr_m_{p['itinerary_id']}")
                                is_manual = True
                            else:
                                # 仿製截圖：切換模式
                                arr_mode = st.radio("模式", ["系統規劃", "手動設定"], index=1 if p.get('use_manual_arr') else 0, horizontal=True, label_visibility="collapsed", key=f"mode_{p['itinerary_id']}")
                                is_manual = (arr_mode == "手動設定")
                                
                                if is_manual:
                                    # 🚀 關鍵優化：手動設定不再是 00:00！而是完美對準目前儲存的時間或系統推算時間
                                    col_arr_h, col_arr_m = st.columns(2)
                                    with col_arr_h:
                                        final_arr_h = st.selectbox("抵達 時", options=list(range(24)), index=saved_arr_h, key=f"arr_h_{p['itinerary_id']}")
                                    with col_arr_m:
                                        final_arr_m = st.selectbox("抵達 分", options=list(range(60)), index=saved_arr_m, key=f"arr_m_{p['itinerary_id']}")
                                else:
                                    # 系統規劃模式下，直接抓系統自動推算的 current_dt 時分，不顯示滾輪
                                    st.info(f"系統自動推算：{arrival_time_str}")
                                    final_arr_h = current_dt.hour
                                    final_arr_m = current_dt.minute
                            
                            st.divider()
                            
                            # --- 第二區：停留時間 ---
                            st.write("⏳ **此景點停留時間**")
                            col_h, col_m = st.columns(2)
                            with col_h:
                                new_h = st.selectbox("時", options=list(range(24)), index=curr_h, key=f"h_{p['itinerary_id']}")
                            with col_m:
                                new_m = st.selectbox("分", options=list(range(60)), index=curr_m, key=f"m_{p['itinerary_id']}")

                            st.divider()
                            st.write("💰 **此景點預估花費**")
                            new_budget = st.number_input(
                                "金額（TWD）",
                                min_value=0,
                                step=50,
                                value=int(p.get('budget', 0) or 0),
                                key=f"budget_{p['itinerary_id']}"
                            )
                                
                            # --- 第三區：儲存按鈕 (還原截圖底部體驗) ---
                            st.write("") # 空一行
                            if st.button("儲存設定", type="primary", use_container_width=True, key=f"save_{p['itinerary_id']}"):
                                p['arr_h'] = final_arr_h
                                p['arr_m'] = final_arr_m
                                p['use_manual_arr'] = is_manual
                                p['stay_h'] = new_h
                                p['stay_m'] = new_m
                                p['budget'] = new_budget
                                
                                st.session_state.my_itinerary[st.session_state.current_day][i] = p
                                auto_save_itinerary()
                                st.rerun()

            st.divider()
            st.subheader("📊 今日概覽")
            active_legs = st.session_state.get('current_directions') or build_offline_legs(iti)
            day_summary = summarize_day(iti, active_legs)
            metric_cols = st.columns(2)
            metric_cols[0].metric("交通時間", format_minutes(day_summary["travel_minutes"]))
            metric_cols[1].metric("停留時間", format_minutes(day_summary["stay_minutes"]))
            metric_cols[0].metric("路線距離", f"{day_summary['distance_km']:.1f} 公里")
            metric_cols[1].metric("預估花費", f"NT$ {day_summary['total_cost']:,}")

            if day_summary["travel_minutes"] > 180:
                st.warning("今天交通時間偏長，建議移除或換天安排 1-2 個景點。")
            elif day_summary["total_minutes"] > 720:
                st.warning("今天行程超過 12 小時，可能會偏趕。")
            elif day_summary["travel_minutes"] > day_summary["stay_minutes"]:
                st.info("今天花在移動的時間比停留時間多，可以考慮把距離較遠的點分到其他天。")
            else:
                st.success("今天的節奏看起來不錯。")
            
            # ==========================================
            # 🚀 順路排序：本機估算優先，Google 最佳化改為手動開啟
            # ==========================================
            st.divider()
            current = st.session_state.current_day

            if len(st.session_state.my_itinerary[current]) >= 3:
                if st.button("🧭 本機順路排序（不使用 API）", type="primary", use_container_width=True):
                    st.session_state.my_itinerary[current] = local_route_order(st.session_state.my_itinerary[current])
                    st.session_state.current_directions = build_offline_legs(st.session_state.my_itinerary[current])
                    auto_save_itinerary()
                    st.toast("✅ 已用本機距離估算重新排序")
                    st.rerun()

                if st.session_state.get("low_api_mode", True):
                    st.caption("Google 最佳化排序目前已隱藏；如需真實道路最佳化，請先關閉側欄的省 API 模式。")
                elif gmaps:
                    if st.button("✨ Google 最佳化排序（會使用 API）", use_container_width=True):
                        with st.spinner("Google 正在計算最佳路徑..."):
                            try:
                                iti = st.session_state.my_itinerary[current]
                                origin = f"{iti[0].get('lat', 24.08)},{iti[0].get('lng', 120.54)}"
                                destination = f"{iti[-1].get('lat', 24.08)},{iti[-1].get('lng', 120.54)}"
                                waypoints = [f"{p.get('lat', 24.08)},{p.get('lng', 120.54)}" for p in iti[1:-1]]

                                directions_result = gmaps.directions(
                                    origin=origin,
                                    destination=destination,
                                    waypoints=waypoints,
                                    optimize_waypoints=True,
                                    mode='driving',
                                    language=api_lang
                                )

                                if directions_result:
                                    optimized_order = directions_result[0]['waypoint_order']
                                    new_iti = [iti[0]]
                                    for idx in optimized_order:
                                        new_iti.append(iti[idx + 1])
                                    new_iti.append(iti[-1])

                                    st.session_state.my_itinerary[current] = new_iti
                                    auto_save_itinerary()
                                    st.toast("✅ Google 最佳化排序完成")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"排序失敗：{e}")
                else:
                    st.caption("尚未設定 GOOGLE_MAPS_API_KEY，因此只能使用本機順路排序。")
            elif len(st.session_state.my_itinerary[current]) > 0:
                st.caption("💡 提示：加入 3 個以上的景點，就能使用順路排序。")

            # ==========================================
            # 📄 功能五：一鍵生成旅遊小書 (PDF) 與分享
            # ==========================================
            st.divider()
            st.subheader("📤 匯出與分享")

            # 1. 內置 PDF 生成函數 (適應 V3 的列表格式)
            def generate_v3_pdf():
                from io import BytesIO
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import cm
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

                font_candidates = [
                    r"C:\Windows\Fonts\msjh.ttc",
                    r"C:\Windows\Fonts\mingliu.ttc",
                    "msjh.ttf",
                ]
                font_path = next((f for f in font_candidates if os.path.exists(f)), None)
                font_name = "Helvetica"
                if font_path:
                    try:
                        pdfmetrics.registerFont(TTFont("ChicTripFont", font_path, subfontIndex=0))
                        font_name = "ChicTripFont"
                    except Exception:
                        font_name = "Helvetica"

                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
                styles = getSampleStyleSheet()
                styles.add(ParagraphStyle(name="CJKTitle", parent=styles["Title"], fontName=font_name, fontSize=18, textColor=colors.HexColor("#1F5F8B")))
                styles.add(ParagraphStyle(name="CJKHeading", parent=styles["Heading2"], fontName=font_name, fontSize=14, textColor=colors.HexColor("#D35400")))
                styles.add(ParagraphStyle(name="CJKBody", parent=styles["BodyText"], fontName=font_name, fontSize=10, leading=15))
                story = [Paragraph(f"我的專屬行程 - {st.session_state.get('explore_city', '智能旅遊')}", styles["CJKTitle"]), Spacer(1, 12)]

                for day_name, day_iti in st.session_state.my_itinerary.items():
                    if not day_iti:
                        continue

                    schedule_rows = build_day_schedule(day_iti, datetime.now().date())
                    offline_legs = build_offline_legs(day_iti)
                    day_summary = summarize_day(day_iti, offline_legs)
                    story.append(Paragraph(f"【 {day_name} 】", styles["CJKHeading"]))

                    table_data = [["時間", "景點", "地址 / 備註", "停留", "花費"]]
                    for i, row in enumerate(schedule_rows):
                        place = row["place"]
                        safe_name = place.get('名稱', '未知景點')
                        safe_address = place.get('地址', '未提供詳細地址')
                        table_data.append([
                            row['start'].strftime('%H:%M'),
                            Paragraph(f"{i+1}. {safe_name}", styles["CJKBody"]),
                            Paragraph(safe_address, styles["CJKBody"]),
                            f"{place.get('stay_h', 1)} 小時 {place.get('stay_m', 0)} 分",
                            f"NT$ {int(place.get('budget', 0) or 0):,}",
                        ])
                        if i < len(offline_legs):
                            leg = offline_legs[i]
                            table_data.append(["", Paragraph(f"前往下一站：{leg['duration']['text']} / {leg['distance']['text']}", styles["CJKBody"]), "", "", ""])

                    table = Table(table_data, colWidths=[1.6 * cm, 4.2 * cm, 6.0 * cm, 2.3 * cm, 2.4 * cm], repeatRows=1)
                    table.setStyle(TableStyle([
                        ("FONTNAME", (0, 0), (-1, -1), font_name),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2F8")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ]))
                    story.extend([
                        table,
                        Spacer(1, 8),
                        Paragraph(f"本日總覽：交通 {format_minutes(day_summary['travel_minutes'])}｜距離 {day_summary['distance_km']:.1f} 公里｜預估花費 NT$ {day_summary['total_cost']:,}", styles["CJKBody"]),
                        Spacer(1, 14),
                    ])

                doc.build(story)
                return buffer.getvalue()

            # 2. 顯示按鈕
            if len(st.session_state.my_itinerary) > 0:
                col_pdf, col_ics, col_line = st.columns(3)
                
                with col_pdf:
                    # 生成並下載 PDF
                    with st.spinner("製作 PDF 中..."):
                        pdf_data = generate_v3_pdf()
                    if pdf_data:
                        st.download_button(
                            label="📥 下載 PDF 行程表",
                            data=pdf_data,
                            file_name="我的旅遊小書.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            type="primary"
                        )
                    else:
                        st.error("PDF 產生失敗，請稍後再試。")

                with col_ics:
                    trip_start_date = st.date_input("行程開始日", value=datetime.now().date(), key="trip_start_date")
                    ics_data = make_ics(st.session_state.my_itinerary, trip_start_date)
                    st.download_button(
                        label="📆 下載行事曆 ICS",
                        data=ics_data,
                        file_name="chictrip_itinerary.ics",
                        mime="text/calendar",
                        use_container_width=True
                    )
                    if st.button("💾 儲存 ICS 到資料夾", use_container_width=True):
                        ics_path = os.path.join(os.getcwd(), "chictrip_itinerary.ics")
                        with open(ics_path, "wb") as f:
                            f.write(ics_data)
                        st.success(f"已儲存：{ics_path}")
                    with st.expander("查看 ICS 內容"):
                        st.code(ics_data.decode("utf-8"), language="text")

                with col_line:
                    share_text = "🚗 分享我的 ChicTrip 多日行程！\n\n"
                    
                    # 第一層迴圈：取出每一天
                    for day_name, day_iti in st.session_state.my_itinerary.items():
                        if day_iti: # 如果那天有排行程才顯示
                            share_text += f"【 {day_name} 】\n"
                            # 第二層迴圈：取出該天的景點
                            for i, p in enumerate(day_iti):
                                share_text += f"{i+1}. {p['名稱']}\n"
                            share_text += "\n" # 每天行程之間空一行，版面更乾淨
                    
                    # 將文字編碼轉為網址格式
                    import urllib.parse
                    encoded_text = urllib.parse.quote(share_text)
                    st.link_button("💬 分享至 LINE", f"https://line.me/R/msg/text/?{encoded_text}", use_container_width=True)
