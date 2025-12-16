import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# ===================== V1.40 (SCMP Direct + Auto Date) =====================
# 這個版本解決了「今日無賽事」導致崩潰的問題
# 它會自動尋找「下一個賽馬日」的數據

st.set_page_config(page_title="賽馬智腦 V1.40", layout="wide")
HKT = timezone(timedelta(hours=8))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ----------------- 核心邏輯：尋找賽事日期 -----------------
def get_next_race_date():
    """
    自動偵測：檢查今天、明天、後天是否有賽程
    回傳：(日期字串 YYYYMMDD, 顯示文字)
    """
    base_date = datetime.now(HKT)
    
    # 檢查未來 3 天
    for i in range(3):
        check_date = base_date + timedelta(days=i)
        date_str = check_date.strftime("%Y%m%d")
        url = f"https://racing.scmp.com/racing/race-card/{date_str}"
        
        try:
            # 只用 HEAD 請求來快速檢查頁面是否存在，減少等待
            resp = requests.head(url, headers=HEADERS, timeout=3)
            if resp.status_code == 200:
                display_text = "今日賽事" if i == 0 else f"預讀：{check_date.strftime('%Y-%m-%d')} (週{'一二三四五六日'[check_date.weekday()]})"
                return date_str, display_text
        except:
            continue
            
    # 如果都找不到，回傳今天（讓程式至少跑起來顯示無數據）
    return base_date.strftime("%Y%m%d"), "暫無近期賽事"

# ----------------- 核心邏輯：SCMP 爬蟲 -----------------
@st.cache_data(ttl=300) # 快取 5 分鐘，避免頻繁請求
def fetch_scmp_race_card(date_str, race_no):
    """
    直接解析 SCMP 的 HTML 表格
    """
    url = f"https://racing.scmp.com/racing/race-card/{date_str}/race/{race_no}"
    log = f"正在連線: {url}\n"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return pd.DataFrame(), f"連線失敗: {resp.status_code}", False

        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 尋找主要的賽事表格
        # SCMP 的結構通常是 div.racecard > table
        tables = soup.find_all('table')
        target_table = None
        
        # 尋找包含 'Horse' 或 '馬名' 的表格
        for t in tables:
            if 'Horse' in t.get_text() or 'Jockey' in t.get_text():
                target_table = t
                break
        
        if not target_table:
            return pd.DataFrame(), "找不到賽事表格 (可能尚未公佈排位)", False

        # 解析表格列
        rows = []
        # 抓取標頭以確定欄位位置
        headers = [th.get_text(strip=True).upper() for th in target_table.find_all('th')]
        
        # 遍歷每一行
        for tr in target_table.find_all('tr')[1:]: # 跳過標頭
            cols = tr.find_all('td')
            if not cols: continue
            
            row_data = [td.get_text(strip=True) for td in cols]
            
            # 確保欄位數量足夠 (SCMP 表格結構可能會變，這裡做彈性處理)
            if len(row_data) > 3:
                # 嘗試提取關鍵資訊
                # 通常第 1 欄是號碼，第 2 欄是馬名(含負重等資訊)
                try:
                    h_no = row_data[0]
                    # 馬名處理：SCMP 有時會把馬名和負重放在一起，需清理
                    full_name = row_data[1] 
                    # 移除括號內的數字 (例如 "ROMANTIC WARRIOR (1)")
                    h_name = full_name.split('(')[0].strip()
                    
                    # 嘗試抓取賠率 (Win Odds)
                    # 賠率通常在最後幾欄，或者標頭為 "ODDS" / "WIN"
                    odds = 0.0
                    odds_str = "-"
                    
                    # 簡單啟發式：找看起來像賠率的數字 (含有小數點)
                    for val in row_data[-3:]: # 檢查最後 3 欄
                        if re.match(r'^\d+\.\d+$', val):
                            odds = float(val)
                            odds_str = val
                            break
                            
                    rows.append({
                        "馬號": h_no,
                        "馬名": h_name,
                        "騎師": row_data[2] if len(row_data) > 2 else "-",
                        "練馬師": row_data[3] if len(row_data) > 3 else "-",
                        "現價": odds,
                        "顯示賠率": odds_str
                    })
                except:
                    continue

        if rows:
            df = pd.DataFrame(rows)
            # 判斷是否有真實賠率
            has_real_odds = df["現價"].sum() > 0
            
            # 如果沒有賠率，生成一個「預測值」欄位讓介面不空白 (可選)
            if not has_real_odds:
                log += "注意：目前尚未有正式賠率 (顯示排位表)\n"
            else:
                log += f"成功獲取賠率數據: {len(df)} 筆\n"
                
            return df, log, has_real_odds
        else:
            return pd.DataFrame(), "解析表格後無數據", False

    except Exception as e:
        return pd.DataFrame(), f"解析錯誤: {str(e)}", False

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.40 (SCMP 直連版)")

# 1. 自動日期偵測
target_date, date_msg = get_next_race_date()
st.info(f"📅 賽程鎖定: **{date_msg}**")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 🎮 控制台")
    race_no = st.selectbox("選擇場次", range(1, 15), index=0)
    
    update_btn = st.button("🔄 讀取數據", type="primary", use_container_width=True)
    
    st.divider()
    st.caption("數據來源: South China Morning Post (SCMP)")
    st.caption("本系統會自動抓取下一個賽馬日的排位表。")

if update_btn:
    with st.spinner("正在連線至 SCMP 資料庫..."):
        df, log, has_odds = fetch_scmp_race_card(target_date, race_no)
        st.session_state['curr_df'] = df
        st.session_state['curr_log'] = log
        st.session_state['has_odds'] = has_odds

# 顯示區域
with col2:
    if 'curr_df' in st.session_state and not st.session_state['curr_df'].empty:
        df = st.session_state['curr_df']
        has_odds = st.session_state.get('has_odds', False)
        
        # 標題
        status_tag = "🟢 即時賠率" if has_odds else "🟡 排位表 (賠率未出)"
        st.subheader(f"第 {race_no} 場 - {status_tag}")
        
        # 顯示卡片 (如果有賠率，顯示推薦)
        if has_odds:
            # 簡單分析：賠率越低分越高
            df["分數"] = df["現價"].apply(lambda x: 100/x if x > 0 else 0)
            best = df.sort_values("分數", ascending=False).iloc[0]
            
            st.markdown(f"""
            <div style="background-color:#e8f5e9; padding:15px; border-radius:10px; border:1px solid #4caf50; margin-bottom:15px;">
                <h4 style="margin:0; color:#2e7d32;">🔥 數據首選</h4>
                <div style="font-size:24px; font-weight:bold; color:#1b5e20;">
                    #{best['馬號']} {best['馬名']} <span style="font-size:16px; color:#666;">(賠率: {best['顯示賠率']})</span>
                </div>
                <div style="font-size:14px;">騎師: {best['騎師']} | 練馬師: {best['練馬師']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("⚠️ 此場次尚未開出正式賠率，僅顯示排位資料。")
            
        # 顯示表格
        st.dataframe(
            df[["馬號", "馬名", "騎師", "練馬師", "顯示賠率"]],
            column_config={
                "馬號": st.column_config.TextColumn("No.", width="small"),
                "顯示賠率": st.column_config.TextColumn("賠率 (Win)", help="若顯示 '-' 代表未開盤"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        with st.expander("查看系統日誌"):
            st.text(st.session_state['curr_log'])
            
    elif 'curr_log' in st.session_state:
        st.error("無法獲取數據，請查看日誌。")
        st.text(st.session_state['curr_log'])
    else:
        st.info("👈 請在左側點擊「讀取數據」開始")
