import streamlit as st
import pandas as pd
import re
import json
import os
import requests
import time
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# 全局設定
HISTORY_FILE = "race_history.json"
HKT = timezone(timedelta(hours=8))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://bet.hkjc.com",
    "Referer": "https://bet.hkjc.com/"
}

# 資源加載
@st.cache_resource
def get_regex():
    return (re.compile(r'^\d+$'), re.compile(r'\d+\.?\d*'), re.compile(r'[\u4e00-\u9fa5]+'))

REGEX_INT, REGEX_FLOAT, REGEX_CHN = get_regex()

@st.cache_resource
def get_storage():
    data = {}
    for i in range(1, 15):
        data[i] = {
            "current_df": pd.DataFrame(),
            "last_df": pd.DataFrame(),
            "last_update": "無數據",
            "raw_info_text": ""
        }
    return data

race_storage = get_storage()

# 評分字典
JOCKEY_RANK = {'Z Purton': 9.2, '潘頓': 9.2, 'J McDonald': 8.5, '麥道朗': 8.5, 'J Moreira': 6.5, '莫雷拉': 6.5, 'H Bowman': 4.8, '布文': 4.8, 'C Y Ho': 4.2, '何澤堯': 4.2, 'K Teetan': 2.8, '田泰安': 2.8}
TRAINER_RANK = {'J Size': 4.4, '蔡約翰': 4.4, 'K W Lui': 4.0, '呂健威': 4.0, 'P C Ng': 2.5, '伍鵬志': 2.5, 'D J Whyte': 2.5, '韋達': 2.5}

# 核心 API 函數 (極簡版)
def fetch_hkjc_data(race_no):
    try:
        today = datetime.now(HKT).strftime("%Y-%m-%d")
        url = "https://bet.hkjc.com/racing/getJSON.aspx"
        
        # 1. 嘗試沙田
        p1 = {"type": "winodds", "date": today, "venue": "ST", "start": race_no, "end": race_no}
        try:
            r = requests.get(url, params=p1, headers=HEADERS, timeout=5)
        except:
            return None, "網絡連線失敗"

        # 2. 檢查數據，如果不行則嘗試跑馬地
        use_hv = False
        if r.status_code != 200:
            use_hv = True
        else:
            if "OUT" not in r.text:
                use_hv = True
        
        if use_hv:
            p2 = {"type": "winodds", "date": today, "venue": "HV", "start": race_no, "end": race_no}
            try:
                r = requests.get(url, params=p2, headers=HEADERS, timeout=5)
            except:
                return None, "網絡連線失敗"
        
        if r.status_code != 200:
            return None, "伺服器錯誤"

        # 3. 解析 JSON
        try:
            data_json = r.json()
        except:
            return None, "非 JSON 格式"
            
        # 4. 提取 OUT 欄位 (分步判斷，避免語法錯誤)
        if data_json is None:
            return None, "空數據"
            
        if "OUT" not in data_json:
            return None, "無賠率數據 (OUT 缺失)"
            
        raw_str = data_json["OUT"]
        parts = raw_str.split(";")
        rows = []
        for item in parts:
            if "=" in item:
                k_v = item.split("=")
                if len(k_v) == 2:
                    k = k_v[0]
                    v = k_v[1]
                    if k.isdigit():
                        try:
                            val = float(v)
                            # 999 代表退賽或未開盤
                            if val < 900:
                                rows.append({"馬號": int(k), "現價": val})
                            else:
                                rows.append({"馬號": int(k), "現價": 0.0})
                        except:
                            pass
        
        if len(rows) > 0:
            df = pd.DataFrame(rows)
            # 補一個默認馬名
            df["馬名"] = df["馬號"].apply(lambda x: "馬匹 " + str(x))
            return df, None
        else:
            return None, "解析後無有效數據"

    except Exception as e:
        return None, str(e)

# 輔助函數
def get_score(row):
    s = 0
    # 賠率分
    o = row.get("現價", 0)
    if o > 0 and o <= 5.0: s += 25
    elif o > 5.0 and o <= 10.0: s += 10
    
    # 走勢分
    t = row.get("走勢", 0)
    if t >= 15: s += 50
    elif t >= 10: s += 35
    elif t >= 5: s += 20
    elif t <= -10: s -= 20
    
    # 人馬分
    j = row.get("騎師", "")
    tr = row.get("練馬師", "")
    for k, v in JOCKEY_RANK.items():
        if k in j or j in k: s += v * 2.5
    for k, v in TRAINER_RANK.items():
        if k in tr or tr in k: s += v * 1.5
        
    return round(s, 1)

def parse_info(text):
    rows = []
    if not text: return pd.DataFrame()
    for line in text.split('\n'):
        parts = line.strip().split()
        if len(parts) >= 3 and parts[0].isdigit():
            try:
                # 簡單抓取：數字是馬號，後面找中文
                no = int(parts[0])
                chn = [p for p in parts if REGEX_CHN.match(p)]
                # 假設第二個中文是騎師，第三個是練馬師 (簡單啟發式)
                if len(chn) >= 2:
                    rows.append({"馬號": no, "騎師": chn[0], "練馬師": chn[1]})
            except: continue
    if rows: return pd.DataFrame(rows)
    return pd.DataFrame()

# 頁面邏輯
st.set_page_config(page_title="HKJC Odds Lite", layout="wide")
st.title("HKJC 賽馬智腦 (Lite)")

with st.sidebar:
    race_no = st.selectbox("場次", range(1, 15))
    if st.button("更新數據"):
        current = race_storage[race_no]
        df_new, err = fetch_hkjc_data(race_no)
        
        if df_new is not None:
            # 計算走勢
            if not current["current_df"].empty:
                last_df = current["current_df"][["馬號", "現價"]].rename(columns={"現價": "上回"})
                df_new = df_new.merge(last_df, on="馬號", how="left")
                df_new["上回"] = df_new["上回"].fillna(df_new["現價"])
                df_new["走勢"] = ((df_new["上回"] - df_new["現價"]) / df_new["上回"] * 100).fillna(0).round(1)
            else:
                df_new["走勢"] = 0.0
            
            # 合併排位資料
            if current["raw_info_text"]:
                info_df = parse_info(current["raw_info_text"])
                if not info_df.empty:
                    df_new = df_new.merge(info_df, on="馬號", how="left").fillna("未知")
            
            current["current_df"] = df_new
            current["last_update"] = datetime.now(HKT).strftime("%H:%M:%S")
            st.success("更新成功")
        else:
            st.error(err)

    # 排位輸入
    current_race = race_storage[race_no]
    new_info = st.text_area("排位資料 (選填)", value=current_race["raw_info_text"], height=100)
    if new_info != current_race["raw_info_text"]:
        current_race["raw_info_text"] = new_info
        st.info("排位資料已暫存，請按「更新數據」生效")

# 主畫面
df = race_storage[race_no]["current_df"]
if not df.empty:
    df["得分"] = df.apply(get_score, axis=1)
    df = df.sort_values("得分", ascending=False)
    
    st.write(f"最後更新: {race_storage[race_no]['last_update']}")
    
    # 顯示 TOP 3
    cols = st.columns(3)
    for i in range(min(3, len(df))):
        row = df.iloc[i]
        cols[i].metric(f"#{row['馬號']}", f"{row['現價']}", f"分: {row['得分']}")
    
    st.dataframe(df, use_container_width=True)
else:
    st.info("暫無數據，請按側邊欄更新按鈕")
