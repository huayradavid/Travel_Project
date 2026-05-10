import streamlit as st
import os
import googlemaps
import pandas as pd
import folium
import polyline
import urllib.parse

from streamlit_folium import st_folium
from dotenv import load_dotenv
from datetime import datetime, timedelta, time
from fpdf import FPDF





# 1. 初始化
load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=API_KEY)

# 初始化 Session State
if 'attractions_df' not in st.session_state:
    st.session_state.attractions_df = None
if 'center_loc' not in st.session_state:
    st.session_state.center_loc = None
if 'route_info' not in st.session_state:
    st.session_state.route_info = None

st.set_page_config(page_title="智能旅遊助手", layout="wide")
st.title("🗺️ 智能旅遊規劃系統")

# --- 2. 側邊欄：進階篩選器 ---
with st.sidebar:
    st.divider()
    st.header("⏰ 時間規劃")
    # 設定出發時間
    start_time = st.time_input("預計出發時間", value=datetime.strptime("09:00", "%H:%M").time())
    ## 建立一個字典來儲存每個景點的停留時間
    stay_durations = {}
    
    if st.session_state.attractions_df is not None:
        with st.expander("⏳ 設定各站停留時間 (分鐘)", expanded=True):
            df = st.session_state.attractions_df
            for i, row in df.iterrows():
                # 為每個景點建立一個獨立的 slider，key 必須唯一
                # 預設值根據類型給予建議（這就是資管系的智慧邏輯！）
                default_stay = 90 if row.get('來源標籤') in ['museum', 'restaurant'] else 60
                stay_durations[row['名稱']] = st.slider(
                    f"{row['名稱']}", 
                    min_value=10, 
                    max_value=240, 
                    value=default_stay, 
                    step=10,
                    key=f"stay_{row['place_id']}"
                )
    st.header("⚙️ 行程規劃設定")
    city = st.text_input("📍 你想去哪裡？", value="彰化市")
    
    # 新增：交通工具切換
    transport_mode = st.selectbox(
        "🚗 交通工具",
        options=["driving", "walking", "bicycling", "transit"],
        format_func=lambda x: {"driving":"開車", "walking":"走路", "bicycling":"自行車", "transit":"大眾運輸"}[x]
    )
    
    # 新增：景點類型篩選 (Google API 支援的類型)
    poi_type = st.multiselect(
        "🏛️ 景點類型 (多選)",
        options=["tourist_attraction", "museum", "park", "amusement_park", "cafe", "restaurant"],
        default=["tourist_attraction"],
        format_func=lambda x: {
            "tourist_attraction":"旅遊景點", "museum":"博物館", 
            "park":"公園", "amusement_park":"遊樂園", 
            "cafe":"咖啡廳", "restaurant":"餐廳"
        }[x]
    )
    
    radius = st.slider("📏 搜尋範圍 (公里)", 1, 20, 5)
    min_rating = st.slider("⭐ 最低評分要求", 3.0, 5.0, 4.2, step=0.1)
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        search_btn = st.button("🔍 搜尋景點")
    with col_btn2:
        route_btn = st.button("🛣️ 優化路徑")

# --- 3. 搜尋邏輯 (技術挑戰版：多類型迴圈搜尋與資料去重) ---
if search_btn:
    try:
        with st.spinner("正在搜尋並整合各類型景點數據..."):
            geocode_result = gmaps.geocode(city)
            if not geocode_result:
                st.error("找不到該地點")
            else:
                st.session_state.center_loc = geocode_result[0]['geometry']['location']
                
                # 建立一個清單來存放所有抓到的原始資料
                all_raw_data = []
                
                # [技術挑戰亮點]：迴圈走訪所有選取的 POI 類型
                for t in poi_type:
                    places_result = gmaps.places_nearby(
                        location=st.session_state.center_loc,
                        radius=radius * 1000,
                        type=t,
                        language='zh-TW'
                    )
                    
                    for place in places_result.get('results', []):
                        # 基礎篩選：評分與評論數(選配)
                        rating = place.get('rating', 0)
                        if rating >= min_rating:
                            all_raw_data.append({
                                '名稱': place['name'],
                                '評分': rating,
                                '地址': place.get('vicinity', '無'),
                                'lat': place['geometry']['location']['lat'],
                                'lng': place['geometry']['location']['lng'],
                                'place_id': place['place_id'], # 用來去重的關鍵 ID
                                '來源標籤': t # 記錄是哪種分類找到的
                            })
                
                if all_raw_data:
                    # 1. 轉化為 DataFrame
                    full_df = pd.DataFrame(all_raw_data)
                    
                    # 2. [技術核心]：資料去重 (Deduplication)
                    # 因為一個景點可能同時符合「旅遊景點」與「博物館」，會被抓到兩次
                    # 我們根據 Google 給的唯一 place_id 來刪除重複項
                    df_unique = full_df.drop_duplicates(subset=['place_id'], keep='first')
                    
                    # 3. 排序並取前 5 名 (或你們想取更多也行)
                    st.session_state.attractions_df = df_unique.sort_values(by='評分', ascending=False).head(5)
                    st.session_state.route_info = None # 重置舊路徑
                    
                    st.toast(f"成功從 {len(poi_type)} 種類型中整合了 {len(df_unique)} 個獨特景點！")
                else:
                    st.warning("目前的篩選條件下找不到任何景點。")

    except Exception as e:
        st.error(f"搜尋過程中發生技術錯誤：{e}")


# --- 4. 路徑規劃邏輯 (修改：支援交通工具切換) ---
if route_btn and st.session_state.attractions_df is not None:
    try:
        with st.spinner("正在計算路徑..."):
            df = st.session_state.attractions_df
            origin = f"{df.iloc[0]['lat']},{df.iloc[0]['lng']}"
            waypoints = [f"{row['lat']},{row['lng']}" for _, row in df.iloc[1:].iterrows()]
            
            directions_result = gmaps.directions(
                origin=origin,
                destination=origin,
                waypoints=waypoints,
                optimize_waypoints=True,
                mode=transport_mode, # 這裡套用使用者選的交通工具
                language="zh-TW"
            )
            st.session_state.route_info = directions_result
            st.success(f"✅ {transport_mode} 路徑計算完成！")
    except Exception as e:
        st.error(f"規劃路徑時出錯：{e}")

# --- 5. 畫面渲染 (加入景點細節資訊) ---
if st.session_state.attractions_df is not None:
    df = st.session_state.attractions_df
    center = st.session_state.center_loc
    
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.subheader("📍 推薦景點與細節")
        
        # [技術優化]：逐一顯示景點卡片與實景照片
        for i, row in df.iterrows():
            with st.expander(f"🔍 {row['名稱']} (評分: {row['評分']} ⭐)"):
                try:
                    # 1. 擴充 fields，把 'photos' 也抓下來
                    details = gmaps.place(
                        place_id=row['place_id'],
                        language='zh-TW',
                        fields=['formatted_phone_number', 'opening_hours', 'website', 'rating', 'review', 'photo']
                    ).get('result', {})
                    
                    # 2. 顯示實景照片 (沉浸式探索核心)
                    if 'photos' in details and len(details['photos']) > 0:
                        # 取得第一張照片的 reference 碼
                        photo_ref = details['photos'][0]['photo_reference']
                        # 組合出 Google Photo API 的網址 (設定最大寬度為 400px)
                        photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={API_KEY}"
                        
                        # 在 Streamlit 中顯示圖片
                        st.image(photo_url, use_container_width=True, caption=f"{row['名稱']} 實景")
                    
                    # 3. 顯示其他資訊 (文字部分並排顯示，節省空間)
                    info_col1, info_col2 = st.columns(2)
                    with info_col1:
                        st.write(f"🏠 **地址：** {row['地址']}")
                        if 'formatted_phone_number' in details:
                            st.write(f"📞 **電話：** {details['formatted_phone_number']}")
                    with info_col2:
                        if 'opening_hours' in details:
                            status = "🟢 營業中" if details['opening_hours'].get('open_now') else "🔴 休息中"
                            st.write(f"⏰ **狀態：** {status}")
                        if 'website' in details:
                            st.link_button("🌐 前往官方網站", details['website'])
                                    
                    # 4. 顯示一則精選評論
                    if 'reviews' in details and len(details['reviews']) > 0:
                        st.divider()
                        st.caption("📝 網友真實評論")
                        st.info(f"「{details['reviews'][0]['text'][:100]}...」")

                    st.write("🚗 **交通接駁服務 (MaaS)**")
                    btn_col1, btn_col2 = st.columns(2)

                    with btn_col1:
                        # Google Maps 導航連結
                        # q: 目的地名稱, destination_place_id: 精確的座標代碼
                        nav_url = f"https://www.google.com/maps/search/?api=1&query={row['名稱']}&query_place_id={row['place_id']}"
                        st.link_button("🚩 開始導航", nav_url, use_container_width=True)

                    with btn_col2:
                        # Uber 深度連結
                        # dlat/dlng: 目的地緯度經度, daddress: 顯示的目的地名稱
                        uber_url = f"https://m.uber.com/ul/?action=setPickup&dlat={row['lat']}&dlng={row['lng']}&daddress={row['名稱']}"
                        st.link_button("🚕 叫 Uber", uber_url, use_container_width=True)
                        
                except Exception as e:
                    st.error(f"無法載入詳細資訊：{e}")
                    
        # --- 顯示路徑順序 (保持原本邏輯) ---
        if st.session_state.route_info:
            st.subheader("⏱️ 建議行程時間軸")
            route = st.session_state.route_info[0]
            legs = route['legs']
            optimized_order = route.get('waypoint_order', [])
            current_time = datetime.combine(datetime.today(), start_time)
            
            # --- 1. 起點 ---
            st.info(f"🕘 **{current_time.strftime('%H:%M')} 出發**")
            st.success(f"🚩 **起點：{df.iloc[0]['名稱']}**")
            
            # 取得起點的停留時間
            first_spot_name = df.iloc[0]['名稱']
            current_time += timedelta(minutes=stay_durations.get(first_spot_name, 60))
            st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;🕒 *在 {first_spot_name} 停留至 {current_time.strftime('%H:%M')}*")
            
            # --- 2. 循環計算中繼站 ---
            for i, waypoint_idx in enumerate(optimized_order):
                # A. 交通
                travel_seconds = legs[i]['duration']['value']
                current_time += timedelta(seconds=travel_seconds)
                
                # B. 抵達
                target_df_idx = waypoint_idx + 1
                spot_name = df.iloc[target_df_idx]['名稱']
                st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;🚗 *交通：{legs[i]['duration']['text']}*")
                st.success(f"📍 **{current_time.strftime('%H:%M')} 抵達：{spot_name}**")
                
                # C. 讀取「該景點專屬」的停留時間
                this_stay = stay_durations.get(spot_name, 60) 
                current_time += timedelta(minutes=this_stay)
                st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;🕒 *計畫停留 {this_stay} 分鐘 (至 {current_time.strftime('%H:%M')})*")
            
            # --- 3. 終點 ---
            final_travel_seconds = legs[-1]['duration']['value']
            current_time += timedelta(seconds=final_travel_seconds)
            st.info(f"🏁 **{current_time.strftime('%H:%M')} 結束行程回到終點**")
            st.success(f"🚩 **終點：{df.iloc[-1]['名稱']}**"    )
            
            
            # 總結亮點
            st.divider()
            total_time_diff = current_time - datetime.combine(datetime.today(), start_time)
            total_hours = total_time_diff.total_seconds() / 3600
            st.metric("行程總耗時", f"{total_hours:.1f} 小時")


            # --- 前面是原本的計算與顯示時間軸的程式碼 ---
            st.divider()
            total_time_diff = current_time - datetime.combine(datetime.today(), start_time)
            total_hours = total_time_diff.total_seconds() / 3600
            st.metric("行程總耗時", f"{total_hours:.1f} 小時")
            
            # ==========================================
            # 🚀 功能五：一鍵生成旅遊小書 (精美 PDF 版)
            # ==========================================
            def generate_itinerary_pdf():
                from fpdf import FPDF
                import os

                # [自動偵測字體檔名]
                possible_fonts = ["msjh.ttf", "msjh.ttc"]
                font_path = None
                
                for f in possible_fonts:
                    if os.path.exists(f):
                        font_path = f
                        break
                        
                if not font_path:
                    st.error("❌ 找不到字體檔！請將 msjh.ttc 或 msjh.ttf 複製到專案資料夾中。")
                    return None

                # --- 2. 自訂 PDF 類別 ---
                class ModernPDF(FPDF):
                    def header(self):
                        # 關鍵修正：在 header 裡也必須註冊並設定字體
                        self.add_font("msjh", "", font_path)
                        self.set_font("msjh", size=18)
                        
                        # 滿版深藍色背景頁首
                        self.set_fill_color(41, 128, 185)
                        self.rect(0, 0, 210, 30, 'F')
                        
                        self.set_y(10)
                        self.set_text_color(255, 255, 255)
                        self.cell(0, 10, txt=f"智能旅遊規劃小書 - {city}", ln=True, align='C')
                        self.set_y(35) 

                    def footer(self):
                        self.set_y(-15)
                        # footer 也需要確保字體存在
                        self.set_font("msjh", size=9)
                        self.set_text_color(150, 150, 150)
                        self.cell(0, 10, txt=f"開發團隊：劉鴻勳、楊譯翔、張綵倪、高暐勳 | 第 {self.page_no()} 頁", align='C')

                # --- 3. 初始化並執行 ---
                try:
                    pdf = ModernPDF()
                    # 註冊中文字體到全域
                    pdf.add_font("msjh", "", font_path)
                    pdf.set_auto_page_break(auto=True, margin=15)
                    pdf.add_page()
                    
                    # --- 4. 摘要資訊區塊 ---
                    pdf.set_font("msjh", size=12)
                    pdf.set_fill_color(240, 245, 250)
                    pdf.set_text_color(80, 80, 80)
                    pdf.cell(0, 12, txt=f"   總計耗時：{total_hours:.1f} 小時  |  出發時間：{start_time.strftime('%H:%M')}", ln=True, fill=True)
                    pdf.ln(5)

                    # --- 5. 時間軸渲染 ---
                    curr_t = datetime.combine(datetime.today(), start_time)
                    x_time = 30 
                    
                    # [起點]
                    first_name = df.iloc[0]['名稱']
                    pdf.set_font("msjh", size=13)
                    pdf.set_text_color(41, 128, 185)
                    pdf.cell(x_time, 10, txt=curr_t.strftime('%H:%M'))
                    pdf.set_text_color(30, 30, 30)
                    pdf.cell(0, 10, txt=f"[出發] {first_name}", ln=True)
                    curr_t += timedelta(minutes=stay_durations.get(first_name, 60))

                    # [中繼站]
                    for i, idx in enumerate(optimized_order):
                        travel_sec = legs[i]['duration']['value']
                        curr_t += timedelta(seconds=travel_sec)
                        
                        # 交通時間
                        pdf.set_font("msjh", size=10)
                        pdf.set_text_color(150, 150, 150)
                        pdf.cell(x_time, 8, txt="")
                        pdf.cell(0, 8, txt=f"|-- 交通：{legs[i]['duration']['text']} ({legs[i]['distance']['text']})", ln=True)
                        
                        # 抵達點
                        spot_name = df.iloc[idx + 1]['名稱']
                        pdf.set_font("msjh", size=13)
                        pdf.set_text_color(46, 204, 113)
                        pdf.cell(x_time, 10, txt=curr_t.strftime('%H:%M'))
                        pdf.set_text_color(30, 30, 30)
                        pdf.cell(0, 10, txt=f"{spot_name}", ln=True)
                        
                        # 停留
                        stay = stay_durations.get(spot_name, 60)
                        curr_t += timedelta(minutes=stay)
                        pdf.set_font("msjh", size=10)
                        pdf.set_text_color(120, 120, 120)
                        pdf.cell(x_time, 8, txt="")
                        pdf.cell(0, 8, txt=f"    * 建議停留：{stay} 分鐘", ln=True)
                    
                    # [終點]
                    pdf.set_text_color(150, 150, 150)
                    pdf.cell(x_time, 8, txt="")
                    pdf.cell(0, 8, txt=f"|-- 回程交通：{legs[-1]['duration']['text']}", ln=True)
                    
                    curr_t += timedelta(seconds=legs[-1]['duration']['value'])
                    pdf.set_font("msjh", size=13)
                    pdf.set_text_color(231, 76, 60)
                    pdf.cell(x_time, 10, txt=curr_t.strftime('%H:%M'))
                    pdf.set_text_color(30, 30, 30)
                    pdf.cell(0, 10, txt=f"[結束] 回到 {first_name}", ln=True)

                    return pdf.output()
                except Exception as e:
                    st.error(f"產生 PDF 時發生錯誤：{e}")
                    return None

            # --- 前面的 generate_itinerary_pdf() 函數保持不變 ---
            
            # 1. 產生 PDF
            pdf_bytes = generate_itinerary_pdf()
            
            # 2. 產生要傳送到 LINE 的文字摘要
            def generate_line_share_text():
                text = f"🚗 我們的【{city}】專屬行程規劃出來囉！\n"
                text += f"⏱️ 預計總耗時：{total_hours:.1f} 小時\n"
                text += "-" * 20 + "\n"
                
                curr_t = datetime.combine(datetime.today(), start_time)
                first_name = df.iloc[0]['名稱']
                text += f"🚩 {curr_t.strftime('%H:%M')} 出發：{first_name}\n"
                curr_t += timedelta(minutes=stay_durations.get(first_name, 60))
                
                for i, idx in enumerate(optimized_order):
                    travel_sec = legs[i]['duration']['value']
                    curr_t += timedelta(seconds=travel_sec)
                    spot_name = df.iloc[idx + 1]['名稱']
                    text += f"📍 {curr_t.strftime('%H:%M')} 抵達：{spot_name}\n"
                    curr_t += timedelta(minutes=stay_durations.get(spot_name, 60))
                
                text += "-" * 20 + "\n"
                text += "💡 詳細的圖文行程與時間軸，請看我傳的 PDF 小書喔！\n"
                text += "(由 資管系智能旅遊系統 自動演算)"
                return text

            # 3. 渲染按鈕區塊 (使用 st.columns 讓按鈕並排)
            if pdf_bytes:
                st.divider()
                st.subheader("📤 匯出與分享")
                
                col_dl, col_share = st.columns(2)
                
                with col_dl:
                    # 原本的 PDF 下載按鈕
                    st.download_button(
                        label="📥 1. 下載精美 PDF 行程",
                        data=bytes(pdf_bytes),
                        file_name=f"{city}_智能行程表.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        type="primary"
                    )
                
                with col_share:
                    # LINE 分享按鈕 (將文字轉為 URL 編碼)
                    share_text = generate_line_share_text()
                    encoded_text = urllib.parse.quote(share_text)
                    line_url = f"https://line.me/R/msg/text/?{encoded_text}"
                    
                    st.link_button(
                        "💬 2. 一鍵分享摘要至 LINE", 
                        line_url, 
                        use_container_width=True
                    )
            # ==========================================

    with col2:
        # 地圖渲染部分 (保持原本的 Google Tiles 和 Polyline 邏輯)
        st.subheader("🗺️ 實時路徑地圖")
        google_tiles = f'https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}&key={API_KEY}'
        m = folium.Map(location=[center['lat'], center['lng']], zoom_start=13, tiles=google_tiles, attr='Google')
        
        for _, row in df.iterrows():
            folium.Marker([row['lat'], row['lng']], popup=row['名稱']).add_to(m)
            
        if st.session_state.route_info:
            encoded_polyline = st.session_state.route_info[0]['overview_polyline']['points']
            route_points = polyline.decode(encoded_polyline)
            folium.PolyLine(route_points, color="#4285F4", weight=6, opacity=0.8).add_to(m)
            
        st_folium(m, width=700, height=550, key="route_map_final")