import streamlit as st
import os
import googlemaps
import folium
from streamlit_folium import st_folium
import polyline
import uuid
import time
from datetime import datetime, time as dt_time, timedelta 
import urllib.parse
from dotenv import load_dotenv




# ==========================================
# 🛡️ 路由守衛 (Route Guard)：檢查是否合法進入
# ==========================================
# 如果 Session 裡面沒有 current_trip_id，代表他不是從首頁按按鈕過來的
if 'current_trip_id' not in st.session_state:
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

# --- 1. 初始化與 API 設定 ---
load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=API_KEY)

st.set_page_config(page_title="智能旅遊筆記", layout="wide")

# 👉 新增：自動儲存函數
def auto_save_itinerary():
    import sqlite3
    import json
    trip_id = st.session_state.get('current_trip_id')
    if trip_id:
        iti_json = json.dumps(st.session_state.my_itinerary, ensure_ascii=False)
        conn = sqlite3.connect('chictrip.db')
        c = conn.cursor()
        c.execute("UPDATE itineraries SET data_json=? WHERE id=?", (iti_json, trip_id))
        conn.commit()
        conn.close()

# --- 2. 初始化 Session State ---
if 'next_page_token' not in st.session_state:
    st.session_state.next_page_token = None
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'my_itinerary' not in st.session_state:
    st.session_state.my_itinerary = []

st.title("🗺️ 智能旅遊規劃系統")
st.markdown("💡 **操作提示：** 在左側搜尋你想去的景點並加入行程，在右側自由拖曳調整順序！")

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
    
    if st.button("💾 手動儲存", use_container_width=True):
        auto_save_itinerary()
        st.success("✅ 行程已成功儲存！")
    if st.button("⬅️ 回到會員首頁", use_container_width=True):
        st.switch_page("Home.py")

# ==========================================
# 📍 左欄：尋找景點 (包含圖文、分頁、雙軌搜尋)
# ==========================================
with col_search:
    st.subheader("🔍 尋找景點")
    # 👉 插入這行：建立一個高度 750px 的獨立滾動視窗
    with st.container(height=750, border=False):
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
                with st.spinner("尋找熱門推薦中..."):
                    try:
                        geocode_result = gmaps.geocode(explore_city)
                        if geocode_result:
                            loc = geocode_result[0]['geometry']['location']
                            # 第一次請求
                            res = gmaps.places_nearby(location=loc, radius=radius_km*1000, type=poi_type, language='zh-TW')
                            
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
                if search_query:
                    with st.spinner("搜尋中..."):
                        try:
                            res = gmaps.places(query=search_query, language='zh-TW')
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
                                language='zh-TW',
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
                    if st.button("➕ 加入行程", key=f"add_{place['place_id']}", type="primary", use_container_width=True):
                        
                        # 🚀 終極殺手鐧：即時資料補水 (Data Hydration)
                        # 直接用 place_id 向 Google 索取最精準的座標！(fields=['geometry'] 可以省 API 費用)
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

    # 建立 Google Maps 底圖
    google_tiles = f'https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}&key={API_KEY}'
    m = folium.Map(location=map_center, zoom_start=zoom_lv, tiles=google_tiles, attr='Google')

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
                    
                    res = gmaps.directions(
                        origin=f"{lat1},{lng1}",
                        destination=f"{lat2},{lng2}",
                        mode=mode,
                        language='zh-TW'
                    )
                    if res:
                        all_legs_info.append(res[0]['legs'][0])
                        points = polyline.decode(res[0]['overview_polyline']['points'])
                        route_points.extend(points)
                        # 畫出該段路線
                        folium.PolyLine(points, color="#4285F4", weight=5, opacity=0.7).add_to(m)
                
                # 存下所有段落的資訊供右欄顯示
                st.session_state.current_directions = all_legs_info
                    
            except Exception as e:
                st.error(f"路徑計算更新中... ({e})")

    # 渲染地圖
    st_folium(m, width="100%", height=600, key="v3_main_map")




# ==========================================
# 📅 右欄：我的行程表 (CRUD 完整邏輯)
# ==========================================
with col_plan:
    st.subheader("📅 我的行程表")

    # ==========================================
    # 📅 天數導覽列 (移至右欄上方)
    # ==========================================
    days = list(st.session_state.my_itinerary.keys())
    
    # 建立兩欄：左邊切換天數，右邊新增天數
    day_col1, day_col2 = st.columns([3, 1])
    
    with day_col1:
        # 使用 selectbox 切換，index 會自動對準目前的 current_day
        current_idx = days.index(st.session_state.current_day) if st.session_state.current_day in days else 0
        new_day_choice = st.selectbox(
            "選擇天數", 
            days, 
            index=current_idx, 
            label_visibility="collapsed", # 隱藏標籤讓畫面更緊湊
            key="day_selector_top"
        )
        # 如果使用者選了不同的天，立刻更新並重新渲染地圖
        if new_day_choice != st.session_state.current_day:
            st.session_state.current_day = new_day_choice
            st.rerun()

    with day_col2:
        if st.button("➕", help="新增天數", use_container_width=True):
            new_day_name = f"第 {len(days) + 1} 天"
            st.session_state.my_itinerary[new_day_name] = []
            st.session_state.current_day = new_day_name
            auto_save_itinerary() # 自動儲存新結構
            st.rerun()
            
    st.divider() # 加一條分隔線，區隔天數控制與下方的行程卡片

    # 👉 同樣插入這行：為行程表建立獨立滾動視窗
    with st.container(height=750, border=False):
        iti = st.session_state.my_itinerary[st.session_state.current_day]

        if not iti:
            st.info("目前行程空空的，從左側加入景點吧！")
        else:
            for i, p in enumerate(iti):

                # 顯示交通資訊 - 彈出式交通設定 (自動儲存版)
                if i > 0:
                    current_mode = p.get('transport_mode', 'driving')
                    mode_options = {"driving": "🚗 開車", "walking": "🚶 步行", "transit": "🚌 大眾運輸", "bicycling": "🚲 單車"}
                    
                    # 抓取預設時間/距離
                    leg_info = "--"
                    if st.session_state.get('current_directions') and i-1 < len(st.session_state.current_directions):
                        leg = st.session_state.current_directions[i-1] # 注意：這裡改為取 list 索引
                        leg_info = f"{leg['duration']['text']} ({leg['distance']['text']})"

                    with st.popover(f"{mode_options.get(current_mode)}：{leg_info} ▾", use_container_width=True):
                    
                        # 👉 修正版：加入 idx 與 key_name 參數，並適配「多日遊」資料結構
                        def update_mode(idx, key_name):
                            new_mode = st.session_state[key_name]
                            # 👉 關鍵防呆：必須先指定「哪一天」，再去改裡面的「第 idx 個景點」
                            current = st.session_state.current_day
                            st.session_state.my_itinerary[current][idx]['transport_mode'] = new_mode
                            auto_save_itinerary()

                        radio_key = f"temp_mode_{p['itinerary_id']}"
                        
                        st.radio(
                            "更改交通方式：",
                            options=list(mode_options.keys()),
                            format_func=lambda x: mode_options[x],
                            index=list(mode_options.keys()).index(current_mode),
                            key=radio_key,
                            on_change=update_mode,
                            # 👉 關鍵：透過 kwargs 強制把「當下的 i」綁定給這個按鈕
                            kwargs={"idx": i, "key_name": radio_key} 
                        )
                        
                        st.divider()
                        # 👉 防呆機制：安全取出上一站與這一站的座標
                        lat1, lng1 = iti[i-1].get('lat', 24.08), iti[i-1].get('lng', 120.54)
                        lat2, lng2 = p.get('lat', 24.08), p.get('lng', 120.54)
                        
                        nav_url = f"https://www.google.com/maps/dir/?api=1&origin={lat1},{lng1}&destination={lat2},{lng2}&travelmode={current_mode}"
                        st.link_button("🚀 開啟導航", nav_url, use_container_width=True)
                
                with st.container(border=True):
                    st.markdown(f"**{i+1}. {p['名稱']}**")
                    c1, c2, c3 = st.columns(3)
                    with c1: 
                        if i > 0 and st.button("⬆️", key=f"u_{p['itinerary_id']}"):
                            iti[i-1], iti[i] = iti[i], iti[i-1]; st.rerun()
                    with c2:
                        if i < len(iti)-1 and st.button("⬇️", key=f"d_{p['itinerary_id']}"):
                            iti[i+1], iti[i] = iti[i], iti[i+1]; st.rerun()
                    with c3:
                        if st.button("❌", key=f"x_{p['itinerary_id']}"):
                            iti.pop(i); st.rerun()
            
            # ==========================================
            # 🚀 Sprint 3：AI 智能排序按鈕 (接在右欄的最後面)
            # ==========================================
            st.divider()
            
            # 取得現在編輯的是哪一天
            current = st.session_state.current_day
            
            # 👉 修正 1：判斷式必須加上 [current]，計算「今天」的景點數
            if len(st.session_state.my_itinerary[current]) >= 3:
                if st.button("✨ 讓 AI 幫我重新順路排序", type="primary", use_container_width=True):
                    with st.spinner("AI 正在計算最佳路徑..."):
                        try:
                            # 👉 修正 2：傳給 AI 的資料也必須加上 [current]
                            iti = st.session_state.my_itinerary[current]
                            
                            # 👉 順便加上防呆機制，避免舊資料讓 AI 當機
                            origin = f"{iti[0].get('lat', 24.08)},{iti[0].get('lng', 120.54)}"
                            destination = f"{iti[-1].get('lat', 24.08)},{iti[-1].get('lng', 120.54)}"
                            waypoints = [f"{p.get('lat', 24.08)},{p.get('lng', 120.54)}" for p in iti[1:-1]]
                            
                            # 呼叫 API
                            directions_result = gmaps.directions(
                                origin=origin,
                                destination=destination,
                                waypoints=waypoints,
                                optimize_waypoints=True, 
                                mode='driving',
                                language='zh-TW'
                            )
                            
                            if directions_result:
                                optimized_order = directions_result[0]['waypoint_order']
                                
                                new_iti = [iti[0]]
                                for idx in optimized_order:
                                    new_iti.append(iti[idx + 1]) 
                                new_iti.append(iti[-1])
                                
                                # 更新 Session State 並自動存檔
                                st.session_state.my_itinerary[current] = new_iti
                                auto_save_itinerary()
                                st.toast("✅ AI 排序完成！請查看新的路線與地圖。")
                                st.rerun() 
                        except Exception as e:
                            st.error(f"排序失敗：{e}")
            
            # 👉 修正 3：這裡的 elif 判斷式也要加上 [current]
            elif len(st.session_state.my_itinerary[current]) > 0:
                st.caption("💡 提示：加入 3 個以上的景點，就能喚醒 AI 智能排序功能喔！")

            # ==========================================
            # 📄 功能五：一鍵生成旅遊小書 (PDF) 與分享
            # ==========================================
            st.divider()
            st.subheader("📤 匯出與分享")

            # 1. 內置 PDF 生成函數 (適應 V3 的列表格式)
            def generate_v3_pdf():
                from fpdf import FPDF
                import os
                
                # 字體檢測
                possible_fonts = ["msjh.ttf", "msjh.ttc"]
                font_path = next((f for f in possible_fonts if os.path.exists(f)), None)
                if not font_path:
                    return None

                class ModernPDF(FPDF):
                    def header(self):
                        self.add_font("msjh", "", font_path)
                        self.set_font("msjh", size=18)
                        self.set_fill_color(41, 128, 185) # 企業藍
                        self.rect(0, 0, 210, 30, 'F')
                        self.set_y(10)
                        self.set_text_color(255, 255, 255)
                        self.cell(0, 10, txt=f"我的專屬行程 - {explore_city if 'explore_city' in locals() else '智能旅遊'}", ln=True, align='C')
                        self.set_y(35)
                    def footer(self):
                        self.set_y(-15)
                        self.set_font("msjh", size=9)
                        self.set_text_color(150, 150, 150)
                        self.cell(0, 10, txt=f"開發團隊：劉鴻勳、楊譯翔、張綵倪、高暐勳 | 第 {self.page_no()} 頁", align='C')

                pdf = ModernPDF()
                pdf.add_font("msjh", "", font_path)
                pdf.add_page()
                
                # 👉 迴圈印出每一天的行程
                for day_name, day_iti in st.session_state.my_itinerary.items():
                    if not day_iti:
                        continue # 如果那天沒排行程就跳過

                    # 印出天數標題 (例如：【 第 1 天 】)
                    pdf.set_font("msjh", size=16)
                    pdf.set_text_color(255, 100, 100)
                    pdf.cell(0, 10, txt=f"【 {day_name} 】", ln=True)
                    pdf.ln(2)

                    for i, place in enumerate(day_iti):
                        # 👉 終極防呆：安全取出名稱與地址
                        safe_name = place.get('名稱', '未知景點')
                        safe_address = place.get('地址', '未提供詳細地址')

                        pdf.set_font("msjh", size=14)
                        pdf.set_text_color(41, 128, 185)
                        pdf.cell(0, 10, txt=f"{i+1}. {safe_name}", ln=True)

                        pdf.set_font("msjh", size=10)
                        pdf.set_text_color(100, 100, 100)
                        pdf.cell(0, 6, txt=f"   🏠 {safe_address}", ln=True)

                        # 如果有設定交通方式，印出對應圖示
                        if i < len(day_iti) - 1:
                            next_mode = day_iti[i+1].get('transport_mode', 'driving')
                            mode_icons = {"driving": "🚗", "walking": "🚶", "transit": "🚌", "bicycling": "🚲"}
                            icon = mode_icons.get(next_mode, "🚗")

                            pdf.ln(2)
                            pdf.set_fill_color(245, 245, 245)
                            pdf.set_text_color(120, 120, 120)
                            pdf.cell(0, 8, txt=f"      {icon} 繼續前往下一站", ln=True, fill=True)
                            pdf.ln(2)
                    
                    pdf.add_page() # 換天的時候幫你換新的一頁
                
                return pdf.output()

            # 2. 顯示按鈕
            if len(st.session_state.my_itinerary) > 0:
                col_pdf, col_line = st.columns(2)
                
                with col_pdf:
                    # 生成並下載 PDF
                    with st.spinner("製作 PDF 中..."):
                        pdf_data = generate_v3_pdf()
                    if pdf_data:
                        st.download_button(
                            label="📥 下載 PDF 行程表",
                            data=bytes(pdf_data),
                            file_name="我的旅遊小書.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            type="primary"
                        )
                    else:
                        st.error("請確認資料夾中有 msjh.ttf 字體")

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