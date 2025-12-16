import streamlit as st
import pandas as pd
import re
import requests
import time
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# ===================== V1.39 進階修復版 =====================
st.set_page_config(page_title="賽馬智腦 Pro", layout="wide")

# 1. 基礎設定
HKT = timezone(timedelta(hours=8))
HEADERS = {"User-Agent": "Mozilla/5.0"}
RACE_STORAGE = {}

if 'race_data' not in st.session_state:
    st.session_state['race_data'] = {}

# 2. 核心函數 (保持扁平)
def get_hkjc_odds(r_no):
    """抓取 HKJC 賠率"""
    try:
        url = "https://bet.hkjc.com/racing/jsonData.aspx"
        params = {
            "type": "winodds", 
            "date": datetime.now(HKT).strftime("%Y-%m-%d"), 
            "venue": "HV", 
            "start": r_no, "end": r_no
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
        # 解析兩種常見格式
        matches = re.findall(r'(\d+)\s*=\s*(\d+\.\d+)', resp.text)
        if not matches:
            matches = re.findall(r'"(\d+)"\s*:\s*"(\d+\.\d+)"', resp.text)
        return {int(m[0]): float(m[1]) for m in matches}
    except:
        return {}

def get_scmp_info(r_no):
    """嘗試抓取馬名 (SCMP)"""
    try:
        date_str = datetime.now(HKT).strftime("%Y%m%d")
        url = f"https://racing.scmp.com/racing/race-card/{date_str}/race/{r_no}"
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text()
            # 簡單正則抓馬名
            # 格式通常是: 1  ROMANTIC WARRIOR
            info = {}
            for line in text.split('\n'):
                m = re.search(r'^(\d{1,2})\s+([A-Z\s\']{3,30})$', line.strip())
                if m and m.group(2) not in ["HORSE", "JOCKEY"]:
                    info[int(m.group(1))] = m.group(2).strip()
            return info
    except:
        pass
    return {}

# 3. 介面邏輯
st.title("🏇 賽馬智腦 V1.39 (功能恢復版)")

col1, col2 = st.columns([1, 2])

with col1:
    race_no = st.selectbox("選擇場次", range(1, 15))
    if st.button("🔄 立即更新數據", type="primary"):
        with st.status("正在抓取數據...", expanded=True) as status:
            # 步驟 1: 抓賠率
            st.write("連線 HKJC...")
            odds_data = get_hkjc_odds(race_no)
            
            # 步驟 2: 抓馬名
            st.write("連線 SCMP (馬名)...")
            name_data = get_scmp_info(race_no)
            
            # 整合
            rows = []
            for h_no, odds in odds_data.items():
                name = name_data.get(h_no, f"馬匹 {h_no}")
                rows.append({"馬號": h_no, "馬名": name, "現價": odds})
            
            if rows:
                df = pd.DataFrame(rows)
                # 計算簡單分數
                df["得分"] = df["現價"].apply(lambda x: 50 if x<5 else (30 if x<10 else 10))
                
                # 計算走勢 (如果有舊數據)
                old_key = f"race_{race_no}"
                if old_key in st.session_state['race_data']:
                    old_df = st.session_state['race_data'][old_key]
                    merged = df.merge(old_df[['馬號', '現價']], on='馬號', suffixes=('', '_old'), how='left')
                    df["走勢"] = ((merged['現價_old'] - merged['現價']) / merged['現價_old'] * 100).fillna(0).round(1)
                else:
                    df["走勢"] = 0.0
                
                st.session_state['race_data'][f"race_{race_no}"] = df
                status.update(label="更新完成", state="complete")
            else:
                status.update(label="找不到數據 (可能今日無賽事)", state="error")

with col2:
    data_key = f"race_{race_no}"
    if data_key in st.session_state['race_data']:
        df = st.session_state['race_data'][data_key]
        df = df.sort_values("現價") # 賠率低到高排序
        
        # 首選卡片
        best = df.iloc[0]
        st.markdown(f"""
        <div style="padding:15px; border-radius:10px; background:#e3f2fd; border:2px solid #2196f3; margin-bottom:15px;">
            <h3 style="margin:0; color:#0d47a1;">🔥 熱門首選：#{best['馬號']} {best['馬名']}</h3>
            <p style="margin:5px 0 0 0; font-size:18px;"><b>{best['現價']}</b> (走勢: {best['走勢']}%)</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 表格
        st.dataframe(
            df, 
            column_config={
                "現價": st.column_config.NumberColumn(format="%.1f"),
                "走勢": st.column_config.NumberColumn(format="%.1f%%"),
                "得分": st.column_config.ProgressColumn(min_value=0, max_value=60)
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("請點擊左側按鈕更新數據")
