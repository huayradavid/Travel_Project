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




# --- 1. 初始化與 API 設定 ---
load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=API_KEY)

st.set_page_config(page_title="智能旅遊筆記", layout="wide")

# --- 1. CSS 介面魔法 (讓地圖固定，左右兩側可捲動) ---
st.markdown("""
    <style>
        /* 隱藏側邊欄的頁面導覽選單 */
        [data-testid="stSidebarNav"] {
            display: none;
        }
        /* 讓左欄和右欄具備固定高度並可獨立捲動 */
        [data-testid="column"]:nth-child(1), [data-testid="column"]:nth-child(3) {
            height: 85vh;
            overflow-y: auto;
            overflow-x: hidden;
            padding-right: 10px;
        }
        /* 中間的地圖欄位固定 */
        [data-testid="column"]:nth-child(2) {
            position: sticky;
            top: 0px;
        }
        /* 美化捲動條 */
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-thumb { background: #888; border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: #555; }
    </style>
""", unsafe_allow_html=True)

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
# 💾 頂部導覽列：回首頁與儲存系統
# ==========================================
col_back, col_title, col_save = st.columns([1, 3, 1])

with col_back:
    if st.button("⬅️ 回到會員首頁", use_container_width=True):
        st.switch_page("Home.py")

with col_title:
    # 顯示目前正在編輯的行程 ID (或是從資料庫撈出來的標題)
    trip_id = st.session_state.get('current_trip_id', '未知')
    st.markdown(f"<h4 style='text-align: center;'>目前編輯行程 ID：{trip_id}</h4>", unsafe_allow_html=True)

with col_save:
    if st.button("💾 儲存行程至雲端", type="primary", use_container_width=True):
        import sqlite3
        import json
        try:
            # 將目前的行程轉成 JSON 格式
            iti_json = json.dumps(st.session_state.my_itinerary, ensure_ascii=False)
            
            # 更新回 SQLite 資料庫
            conn = sqlite3.connect('chictrip.db')
            c = conn.cursor()
            c.execute("UPDATE itineraries SET data_json=? WHERE id=?", (iti_json, trip_id))
            conn.commit()
            conn.close()
            
            st.toast("✅ 行程已成功儲存至資料庫！")
        except Exception as e:
            st.error(f"儲存失敗：{e}")




# ==========================================
# 📍 左欄：尋找景點 (包含圖文、分頁、雙軌搜尋)
# ==========================================
with col_search:
    st.subheader("🔍 尋找景點")
    
    tab_explore, tab_search = st.tabs(["💡 探索推薦", "🎯 精準搜尋"])
    
    # --- 標籤 1：探索推薦 ---
    with tab_explore:
        explore_city = st.text_input("想探索哪個區域？", value="彰化市", key="explore_city")
        poi_type = st.selectbox("景點類型", ["tourist_attraction", "restaurant", "cafe"], 
                                format_func=lambda x: {"tourist_attraction":"旅遊景點", "restaurant":"餐廳", "cafe":"咖啡廳"}[x])
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
                
                # 加入行程按鈕 (使用穩定 Key)
                if st.button("➕ 加入行程", key=f"add_{place['place_id']}_{i}", use_container_width=True):
                    new_item = place.copy()
                    new_item['itinerary_id'] = str(uuid.uuid4())
                    st.session_state.my_itinerary.append(new_item)
                    st.toast(f"✅ 已加入：{place['名稱']}")
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
    
    itinerary = st.session_state.my_itinerary
    
    # 設定地圖中心點（預設為彰化市，或行程第一個點）
    if itinerary:
        map_center = [itinerary[0]['lat'], itinerary[0]['lng']]
        zoom_lv = 14
    else:
        map_center = [24.08, 120.54] # 彰化預設座標
        zoom_lv = 13

    # 建立 Google Maps 底圖
    google_tiles = f'https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}&key={API_KEY}'
    m = folium.Map(location=map_center, zoom_start=zoom_lv, tiles=google_tiles, attr='Google')

    if len(itinerary) > 0:
        # 1. 繪製景點標記 (加上數字序號)
        for i, place in enumerate(itinerary):
            folium.Marker(
                [place['lat'], place['lng']],
                popup=f"{i+1}. {place['名稱']}",
                tooltip=f"第 {i+1} 站",
                icon=folium.DivIcon(html=f"""
                    <div style="
                        font-family: sans-serif; 
                        color: white; 
                        background-color: #4285F4; 
                        border-radius: 50%; 
                        width: 24px; 
                        height: 24px; 
                        display: flex; 
                        justify-content: center; 
                        align-items: center;
                        font-weight: bold;
                        border: 2px solid white;
                        box-shadow: 0px 2px 4px rgba(0,0,0,0.3);
                    ">{i+1}</div>""")
            ).add_to(m)

        # 2. 繪製真實道路連線 (當至少有兩個點時)
        if len(itinerary) >= 2:
            try:
                # 依序抓取座標
                origin = f"{itinerary[0]['lat']},{itinerary[0]['lng']}"
                destination = f"{itinerary[-1]['lat']},{itinerary[-1]['lng']}"
                
                # 如果有中間站
                waypoints = [f"{p['lat']},{p['lng']}" for p in itinerary[1:-1]]
                
                # 注意：這裡 optimize_waypoints=False，因為我們是要「呈現使用者排好的順序」
                directions_result = gmaps.directions(
                    origin=origin,
                    destination=destination,
                    waypoints=waypoints,
                    optimize_waypoints=False, 
                    mode='driving',
                    language='zh-TW'
                )

                if directions_result:
                    # 解碼 Google 回傳的加密路徑
                    encoded_polyline = directions_result[0]['overview_polyline']['points']
                    route_points = polyline.decode(encoded_polyline)
                    
                    # 在地圖上畫出連線
                    folium.PolyLine(
                        route_points, 
                        color="#4285F4", 
                        weight=6, 
                        opacity=0.8
                    ).add_to(m)
                    
                    # 儲存路徑資訊供右欄顯示時間 (選配)
                    st.session_state.current_directions = directions_result
                    
            except Exception as e:
                st.error(f"地圖路線生成失敗：{e}")

    # 渲染地圖
    st_folium(m, width="100%", height=600, key="v3_main_map")




# ==========================================
# 📅 右欄：我的行程表 (CRUD 完整邏輯)
# ==========================================
with col_plan:
    st.subheader("📅 我的行程表")
    iti = st.session_state.my_itinerary

    if not iti:
        st.info("目前行程空空的，從左側加入景點吧！")
    else:
        for i, p in enumerate(iti):
            # 顯示交通資訊 (如果有上一站)
            if i > 0 and st.session_state.current_directions:
                leg = st.session_state.current_directions[0]['legs'][i-1]
                st.markdown(f"<div style='text-align:center; color:gray; font-size:0.8rem;'>🚗 {leg['duration']['text']} ({leg['distance']['text']})</div>", unsafe_allow_html=True)
            
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
        
        # 至少要有 3 個點以上（起點、終點、中繼站）才需要排序
        if len(st.session_state.my_itinerary) >= 3:
            if st.button("✨ 讓 AI 幫我重新順路排序", type="primary", use_container_width=True):
                with st.spinner("AI 正在計算最佳路徑..."):
                    try:
                        iti = st.session_state.my_itinerary
                        # 我們固定使用者的「第1個點」為起點，「最後1個點」為終點，中間的點讓 AI 去排
                        origin = f"{iti[0]['lat']},{iti[0]['lng']}"
                        destination = f"{iti[-1]['lat']},{iti[-1]['lng']}"
                        waypoints = [f"{p['lat']},{p['lng']}" for p in iti[1:-1]]
                        
                        # 呼叫 API，並開啟 optimize_waypoints=True
                        directions_result = gmaps.directions(
                            origin=origin,
                            destination=destination,
                            waypoints=waypoints,
                            optimize_waypoints=True, 
                            mode='driving',
                            language='zh-TW'
                        )
                        
                        if directions_result:
                            # 取得 AI 建議的順序 (這是相對於 waypoints 陣列的索引)
                            optimized_order = directions_result[0]['waypoint_order']
                            
                            # 重新排列行程表
                            # 起點不變
                            new_iti = [iti[0]]
                            # 根據 AI 給的順序放入中繼站
                            for idx in optimized_order:
                                new_iti.append(iti[idx + 1]) 
                            # 終點不變
                            new_iti.append(iti[-1])
                            
                            # 更新 Session State
                            st.session_state.my_itinerary = new_iti
                            st.toast("✅ AI 排序完成！請查看新的路線與地圖。")
                            st.rerun() # 重新渲染畫面
                    except Exception as e:
                        st.error(f"排序失敗：{e}")
        elif len(st.session_state.my_itinerary) > 0:
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
            pdf.set_font("msjh", size=12)

            iti = st.session_state.my_itinerary
            # 獲取導航資訊 (包含交通時間)
            directions = st.session_state.get('current_directions')
            
            for i, place in enumerate(iti):
                # 景點標題
                pdf.set_font("msjh", size=14)
                pdf.set_text_color(41, 128, 185)
                pdf.cell(0, 10, txt=f"{i+1}. {place['名稱']}", ln=True)
                
                # 景點地址
                pdf.set_font("msjh", size=10)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 6, txt=f"   🏠 {place['地址']}", ln=True)
                
                # 如果有下一站，顯示交通資訊
                if directions and i < len(iti) - 1:
                    leg = directions[0]['legs'][i]
                    pdf.ln(2)
                    pdf.set_fill_color(245, 245, 245)
                    pdf.set_text_color(120, 120, 120)
                    pdf.cell(0, 8, txt=f"      🚗 交通：{leg['duration']['text']} ({leg['distance']['text']})", ln=True, fill=True)
                    pdf.ln(2)
            
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
                # LINE 分享
                import urllib.parse
                share_text = f"分享我的旅遊行程！\n"
                for i, p in enumerate(st.session_state.my_itinerary):
                    share_text += f"{i+1}. {p['名稱']}\n"
                encoded_text = urllib.parse.quote(share_text)
                st.link_button("💬 分享至 LINE", f"https://line.me/R/msg/text/?{encoded_text}", use_container_width=True)