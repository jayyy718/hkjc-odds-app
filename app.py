import streamlit as st
import pandas as pd
import re

# ===================== V1.60 (Admin/User Mode) =====================
# 核心理念：完全不連網，依賴管理員手動貼上資料
# 1. 貼上排位表 (來自賽馬天地或其他網站)
# 2. 貼上賠率表 (來自馬會官網)
# 3. 系統自動合併並展示

st.set_page_config(page_title="賽馬智腦 V1.60", layout="wide")

# 初始化 Session State (模擬資料庫)
if 'race_data' not in st.session_state:
    st.session_state['race_data'] = None
if 'last_update' not in st.session_state:
    st.session_state['last_update'] = None

# ----------------- 解析邏輯 -----------------

def parse_card_text(text):
    """
    解析排位表文字
    假設格式大致為： 1 浪漫勇士 6 135 潘頓 沈集成
    (馬號 馬名 檔位 負磅 騎師 練馬師)
    """
    data = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 嘗試抓取關鍵欄位
        # 尋找開頭是數字 (馬號)
        # 然後尋找中文 (馬名, 騎師, 練馬師)
        # 尋找其他數字 (檔位, 負磅)
        
        try:
            parts = line.split()
            if not parts[0].isdigit(): continue
            
            h_no = int(parts[0])
            
            # 簡單啟發式分析 (Heuristic Analysis)
            # 這需要根據您複製的網站格式稍作調整，這裡是用最通用的邏輯
            # 假設第二個非數字塊是馬名
            
            row = {'馬號': h_no, '原始資料': line}
            
            # 嘗試提取馬名 (純中文)
            chinese_parts = [p for p in parts if re.search(r'[\u4e00-\u9fa5]', p)]
            if len(chinese_parts) >= 1: row['馬名'] = chinese_parts[0]
            if len(chinese_parts) >= 2: row['騎師'] = chinese_parts[1]
            if len(chinese_parts) >= 3: row['練馬師'] = chinese_parts[2]
            
            # 嘗試提取檔位和負磅 (除了馬號以外的數字)
            num_parts = [p for p in parts if p.isdigit() and int(p) != h_no]
            # 簡單判斷：小的通常是檔位(1-14)，大的通常是負磅(100-135)
            for n in num_parts:
                val = int(n)
                if 1 <= val <= 14 and '檔位' not in row: row['檔位'] = val
                elif 100 <= val <= 135 and '負磅' not in row: row['負磅'] = val
            
            data.append(row)
        except:
            continue
            
    return pd.DataFrame(data)

def parse_odds_text(text):
    """
    解析賠率文字
    格式： 1 2.5
    """
    odds_map = {}
    lines = text.strip().split('\n')
    
    for line in lines:
        # 尋找行內的 [數字] ... [小數點數字]
        # Regex: 開頭數字(Group 1) ... 小數點數字(Group 2)
        match = re.search(r'^(\d+)\s+.*?(\d+\.\d+)', line)
        if not match:
            # 嘗試更寬鬆的匹配: 只要有數字和小數點
            nums = re.findall(r'\d+\.\d+|\d+', line)
            if len(nums) >= 2:
                try:
                    h_no = int(nums[0])
                    # 倒著找第一個有小數點的
                    h_win = None
                    for n in reversed(nums):
                        if '.' in n: 
                            h_win = float(n)
                            break
                    if h_no and h_win: odds_map[h_no] = h_win
                except: pass
        else:
            try:
                odds_map[int(match.group(1))] = float(match.group(2))
            except: pass
            
    return odds_map

# ----------------- 側邊欄：身份切換 -----------------
mode = st.sidebar.radio("身份選擇", ["👨‍💻 一般用戶 (查看)", "🔧 管理員 (輸入資料)"])

# ----------------- 頁面邏輯 -----------------

if mode == "🔧 管理員 (輸入資料)":
    st.title("🔧 後台管理系統")
    st.write("請在此輸入資料，點擊發布後，一般用戶即可看到分析結果。")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("步驟 1：貼上排位表 (來自賽馬天地/HKJC)")
        card_text = st.text_area("排位文字", height=300, placeholder="1 浪漫勇士 1 126 麥道朗 沈集成\n2 金鎗六十 2 126 何澤堯 呂健威\n...")
        
    with col2:
        st.info("步驟 2：貼上賠率 (來自馬會/頭條)")
        odds_text = st.text_area("賠率文字", height=300, placeholder="1 2.3\n2 5.6\n...")
        
    if st.button("🚀 發布/更新資料", type="primary"):
        if not card_text:
            st.error("請至少貼上排位表！")
        else:
            # 1. 解析排位
            df_card = parse_card_text(card_text)
            
            # 2. 解析賠率 (如果有)
            if odds_text:
                odds_map = parse_odds_text(odds_text)
                df_card['獨贏'] = df_card['馬號'].map(odds_map).fillna("-")
            else:
                df_card['獨贏'] = "未輸入"
                
            # 3. 儲存到全局變數
            st.session_state['race_data'] = df_card
            st.session_state['last_update'] = pd.Timestamp.now().strftime("%H:%M:%S")
            st.success(f"已成功發布 {len(df_card)} 匹馬的資料！請切換至「一般用戶」查看效果。")

else: # 一般用戶模式
    st.title("🏇 賽馬智腦 V1.60 (公開版)")
    
    if st.session_state['race_data'] is None:
        st.warning("⏳ 管理員尚未發布本場賽事資料，請稍後再試。")
        st.info("提示：請先切換到左側 sidebar 的「管理員」模式輸入資料。")
    else:
        df = st.session_state['race_data'].copy()
        update_time = st.session_state['last_update']
        
        st.caption(f"最後更新時間: {update_time}")
        
        # 智能分析：如果有賠率，算出大熱門
        try:
            valid_odds = df[pd.to_numeric(df['獨贏'], errors='coerce').notnull()].copy()
            if not valid_odds.empty:
                valid_odds['v'] = valid_odds['獨贏'].astype(float)
                valid_odds = valid_odds.sort_values('v')
                
                # Top 3
                top3 = valid_odds.head(3)
                
                c1, c2, c3 = st.columns(3)
                if len(top3) > 0:
                    c1.metric("🥇 第一熱門", f"#{top3.iloc[0]['馬號']} {top3.iloc[0].get('馬名', '')}", f"{top3.iloc[0]['獨贏']}")
                if len(top3) > 1:
                    c2.metric("🥈 第二熱門", f"#{top3.iloc[1]['馬號']} {top3.iloc[1].get('馬名', '')}", f"{top3.iloc[1]['獨贏']}")
                if len(top3) > 2:
                    c3.metric("🥉 第三熱門", f"#{top3.iloc[2]['馬號']} {top3.iloc[2].get('馬名', '')}", f"{top3.iloc[2]['獨贏']}")
                
                st.markdown("---")
        except: pass
        
        # 顯示主表格
        # 整理欄位順序
        preferred_cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位', '負磅']
        # 只顯示存在的欄位
        final_cols = [c for c in preferred_cols if c in df.columns]
        
        # 美化表格顯示
        st.dataframe(
            df[final_cols],
            column_config={
                "獨贏": st.column_config.TextColumn("獨贏賠率", help="即時獨贏賠率"),
                "馬號": st.column_config.NumberColumn("No.", format="%d"),
            },
            use_container_width=True,
            hide_index=True
        )
