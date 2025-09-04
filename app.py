import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import sqlite3
import time
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from fuzzywuzzy import process
from datetime import datetime

# 應用標題
st.title("Taiwan Stock Tracker V1.0")

# 完整 TWSE 股票清單
stock_list = {
    '2330.TW': 'Taiwan Semiconductor Manufacturing Company Limited',
    '2317.TW': 'Hon Hai Precision Industry Co., Ltd.',
    '2454.TW': 'MediaTek Inc.',
    '2308.TW': 'Delta Electronics, Inc.',
    '2881.TW': 'Fubon Financial Holding Co., Ltd.',
    '2412.TW': 'Chunghwa Telecom Co., Ltd.',
    '2382.TW': 'Quanta Computer Inc.',
    '2882.TW': 'Cathay Financial Holding Co., Ltd.',
    '2882A.TW': 'Cathay Financial Holding Co., Ltd. A',
    '2882B.TW': 'Cathay Financial Holding Co., Ltd. B',
    '2891.TW': 'CTBC Financial Holding Co., Ltd.',
    '3711.TW': 'ASE Technology Holding Co., Ltd.',
    '2886.TW': 'Mega Financial Holding Co., Ltd.',
    '6669.TW': 'Wiwynn Corporation',
    '2345.TW': 'Accton Technology Corporation',
    '2303.TW': 'United Microelectronics Corporation',
    '2357.TW': 'ASUSTeK Computer Inc.',
    '1216.TW': 'Uni-President Enterprises Corp.',
    '2885.TW': 'Yuanta Financial Holding Co., Ltd.',
    '2887.TW': 'TS Financial Holding Co., Ltd.',
    '2892.TW': 'First Financial Holding Co., Ltd.',
    '2383.TW': 'Elite Material Co., Ltd.',
    '2880.TW': 'Hua Nan Financial Holdings Co., Ltd.',
    '2603.TW': 'Evergreen Marine Corporation (Taiwan) Ltd.',
    '6919.TW': 'Caliway Biopharmaceuticals Co., Ltd.',
    '5880.TW': 'Taiwan Cooperative Financial Holding Co., Ltd.',
    '6505.TW': 'Formosa Petrochemical Corporation',
    '3017.TW': 'Asia Vital Components Co., Ltd.',
    '3231.TW': 'Wistron Corporation',
    '3661.TW': 'Alchip Technologies, Limited',
    '3045.TW': 'Taiwan Mobile Co., Ltd.',
    '3653.TW': 'Jentech Precision Industrial Co., Ltd.',
    '2890.TW': 'SinoPac Financial Holdings Company Limited',
    '3008.TW': 'LARGAN Precision Co., Ltd.',
    '1303.TW': 'Nan Ya Plastics Corporation',
    '2207.TW': 'Hotai Motor Co., Ltd.',
    '4904.TW': 'Far EasTone Telecommunications Co., Ltd.',
    '2002.TW': 'China Steel Corporation',
    '2059.TW': 'King Slide Works Co., Ltd.',
    '2395.TW': 'Advantech Co., Ltd.',
    '2883.TW': 'KGI Financial Holding Co., Ltd.',
    '2301.TW': 'Lite-On Technology Corporation',
    '2379.TW': 'Realtek Semiconductor Corp.',
    '2327.TW': 'Yageo Corporation',
    '3034.TW': 'Novatek Microelectronics Corp.',
    '2912.TW': 'President Chain Store Corporation',
    '910322.TW': 'Tingyi (Cayman Islands) Holding Corp.',
    '1301.TW': 'Formosa Plastics Corporation',
    '2360.TW': 'Chroma ATE Inc.',
    '2801.TW': 'Chang Hwa Commercial Bank, Ltd.',
    '2615.TW': 'Wan Hai Lines Ltd.',
    '2368.TW': 'Gold Circuit Electronics Ltd.',
    '2618.TW': 'EVA Airways Corp.',
    '3037.TW': 'Unimicron Technology Corp.',
    '2609.TW': 'Yang Ming Marine Transport Corporation',
    '5876.TW': 'The Shanghai Commercial & Savings Bank, Ltd.',
    '2404.TW': 'United Integrated Services Co., Ltd.',
    '5871.TW': 'Chailease Holding Company Limited',
    '2449.TW': 'King Yuan Electronics Co., Ltd.',
    '3665.TW': 'Bizlink Holding Inc.',
    '4938.TW': 'Pegatron Corporation',
    '2376.TW': 'Giga-Byte Technology Co., Ltd.',
    '3443.TW': 'Global Unichip Corp.',
    '4958.TW': 'Zhen Ding Technology Holding Limited',
}

# 檢查機制 1：標準化與驗證股票代碼（縮排已修正）
def validate_stock_code(query):
    if query.isdigit() and len(query) == 4:
        query = f"{query}.TW"
    if query in stock_list:
        return query
    try:
        ticker = yf.Ticker(query)
        info = ticker.info
        if info.get('regularMarketPrice') is not None:
            return query
    except:
        pass
    return None

# 檢查機制 2：模糊查詢股票名稱
def fuzzy_search_name(query):
    matches = process.extract(query, stock_list.values(), limit=3)
    if matches and matches[0][1] > 80:  # 匹配度 > 80%
        matched_name = matches[0][0]
        return [k for k, v in stock_list.items() if v == matched_name][0]
    else:
        return None, matches

# 資料庫初始化（包含投資清單表）
def init_database(db_path):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # 股票價格資料表
        c.execute('''
            CREATE TABLE IF NOT EXISTS stock_data (
                symbol TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER
            )
        ''')
        # 投資清單資料表
        c.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                quantity INTEGER
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Database initialization failed: {str(e)}")

# 儲存股票價格到資料庫
def save_to_database(db_path, symbol, data):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        for index, row in data.iterrows():
            date_str = index.strftime('%Y-%m-%d %H:%M:%S')
            c.execute('''
                INSERT OR REPLACE INTO stock_data (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, date_str, row['Open'], row['High'], row['Low'], row['Close'], row['Volume']))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Failed to save data to database: {str(e)}")

# 從資料庫讀取股票價格
def load_from_database(db_path, symbol):
    try:
        conn = sqlite3.connect(db_path)
        query = f"SELECT * FROM stock_data WHERE symbol = ? ORDER BY date DESC LIMIT 100"
        df = pd.read_sql_query(query, conn, params=(symbol,))
        conn.close()
        return df
    except Exception as e:
        st.error(f"Failed to load data from database: {str(e)}")
        return pd.DataFrame()

# 新增到投資清單
def add_to_portfolio(db_path, symbol, name, quantity):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO portfolio (symbol, name, quantity)
            VALUES (?, ?, ?)
        ''', (symbol, name, quantity))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Failed to add to portfolio: {str(e)}")

# 從資料庫載入投資清單
def load_portfolio(db_path):
    try:
        conn = sqlite3.connect(db_path)
        query = "SELECT symbol, name, quantity FROM portfolio"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Failed to load portfolio: {str(e)}")
        return pd.DataFrame(columns=["symbol", "name", "quantity"])

# 儲存編輯後的投資清單
def save_portfolio_changes(db_path, edited_df):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # 清空現有資料
        c.execute("DELETE FROM portfolio")
        # 儲存新資料
        for _, row in edited_df.iterrows():
            c.execute('''
                INSERT INTO portfolio (symbol, name, quantity)
                VALUES (?, ?, ?)
            ''', (row['symbol'], row['name'], row['quantity']))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Failed to save portfolio changes: {str(e)}")

# 抓取並顯示股票數據
def fetch_and_display_data(stock_symbol):
    try:
        init_database(db_path)
        ticker = yf.Ticker(stock_symbol)
        info = ticker.info
        intraday_data = yf.download(stock_symbol, period="1d", interval="1m")
        history_data = yf.download(stock_symbol, period="1mo", interval="1d")
        if intraday_data.empty or history_data.empty:
            st.error("No data found for this symbol. Please check the symbol.")
            return
        save_to_database(db_path,