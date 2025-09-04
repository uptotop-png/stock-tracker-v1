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
import os

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

# 檢查機制 1：標準化與驗證股票代碼
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
        # 確保資料庫檔案路徑可寫
        if not os.path.exists(os.path.dirname(db_path)) and os.path.dirname(db_path):
            os.makedirs(os.path.dirname(db_path))
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
        st.success(f"Database initialized successfully at {db_path}")
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
        save_to_database(db_path, stock_symbol, intraday_data)
        current_price = intraday_data['Close'].iloc[-1]
        previous_close = info.get('regularMarketPreviousClose', 'N/A')
        change = current_price - previous_close if previous_close != 'N/A' else 'N/A'
        percent_change = (change / previous_close * 100) if previous_close != 'N/A' else 'N/A'
        if alert_price > 0 and current_price >= alert_price:
            alert_msg = f"{stock_symbol} price reached {current_price:.2f} TWD, above your alert threshold {alert_price} TWD!"
            alert_placeholder.warning(alert_msg)
        sma_5 = SMAIndicator(history_data['Close'], window=5).sma_indicator()
        sma_20 = SMAIndicator(history_data['Close'], window=20).sma_indicator()
        rsi_14 = RSIIndicator(history_data['Close'], window=14).rsi()
        with info_placeholder.container():
            st.subheader(f"{info.get('longName', stock_symbol)} ({stock_symbol})")
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Price", f"{current_price:.2f} TWD")
            col2.metric("Change", f"{change:.2f} ({percent_change:.2f}%)" if change != 'N/A' else 'N/A')
            col3.metric("Volume", f"{intraday_data['Volume'].iloc[-1]:,}")
            st.write(f"52-Week High: {info.get('fiftyTwoWeekHigh', 'N/A')}")
            st.write(f"52-Week Low: {info.get('fiftyTwoWeekLow', 'N/A')}")
            st.write(f"SMA (5-day): {sma_5.iloc[-1]:.2f}")
            st.write(f"SMA (20-day): {sma_20.iloc[-1]:.2f}")
            st.write(f"RSI (14-day): {rsi_14.iloc[-1]:.2f}")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=intraday_data.index,
                                     open=intraday_data['Open'],
                                     high=intraday_data['High'],
                                     low=intraday_data['Low'],
                                     close=intraday_data['Close'],
                                     name='Stock Price'))
        fig.add_trace(go.Scatter(x=history_data.index, y=sma_5, name='SMA 5', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=history_data.index, y=sma_20, name='SMA 20', line=dict(color='orange')))
        fig.update_layout(title=f"{stock_symbol} Chart with SMA",
                          xaxis_title="Time",
                          yaxis_title="Price (TWD)",
                          xaxis_rangeslider_visible=True)
        with chart_placeholder.container():
            st.plotly_chart(fig, use_container_width=True)
        db_data = load_from_database(db_path, stock_symbol)
        if not db_data.empty:
            with db_placeholder.container():
                st.subheader("Stored Data (Last 100 Records)")
                st.dataframe(db_data[['date', 'open', 'high', 'low', 'close', 'volume']])
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")

# 新函數：處理輸入
def process_input(query):
    stock_symbol = validate_stock_code(query)
    if not stock_symbol:
        matched_symbol, matches = fuzzy_search_name(query)
        if matched_symbol:
            stock_symbol = matched_symbol
        else:
            st.warning("No exact match found. Did you mean:")
            for match in matches:
                st.write(f"- {match[0]} (Similarity: {match[1]}%)")
            st.stop()
    return stock_symbol

# 用戶輸入
st.header("Stock Price Tracker")
query = st.text_input("Enter Stock Code (e.g., 2330) or Name (e.g., Taiwan Semiconductor)", value="2330")
update_mode = st.radio("Update Mode", ("Manual (Button)", "Auto (Polling every 10 seconds)"))
alert_price = st.number_input("Set Alert Price (TWD)", min_value=0.0, value=0.0, step=0.1)
db_path = st.text_input("Database File Path", value="stock_data.db")

# 投資清單輸入
st.header("Manage Your Portfolio")
new_stock_code = st.text_input("Add Stock Code (e.g., 2330)", key="new_stock")
new_quantity = st.number_input("Add Quantity (Shares)", min_value=0, value=0, step=1)
if st.button("Add to Portfolio"):
    if new_stock_code:
        stock_symbol = validate_stock_code(new_stock_code)
        if stock_symbol and new_quantity > 0:
            stock_name = stock_list.get(stock_symbol, stock_symbol)
            add_to_portfolio(db_path, stock_symbol, stock_name, new_quantity)
            st.success(f"Added {stock_name} ({stock_symbol}) with {new_quantity} shares to portfolio!")
        else:
            st.error("Invalid stock code or quantity. Please check and try again.")

# 顯示佔位符
info_placeholder = st.empty()
chart_placeholder = st.empty()
alert_placeholder = st.empty()
db_placeholder = st.empty()
portfolio_placeholder = st.empty()

# 主程式：處理輸入並顯示數據
stock_symbol = process_input(query)
if stock_symbol:
    if update_mode == "Manual (Button)":
        if st.button("Update Data"):
            fetch_and_display_data(stock_symbol)
    else:
        fetch_and_display_data(stock_symbol)
        time.sleep(10)
        st.rerun()

# 顯示並編輯投資清單
with portfolio_placeholder.container():
    st.subheader("Your Portfolio")
    portfolio_df = load_portfolio(db_path)
    if not portfolio_df.empty:
        edited_df = st.data_editor(
            portfolio_df,
            num_rows="dynamic",  # 允許新增和刪除列
            column_config={
                "symbol": st.column_config.TextColumn("Stock Code", disabled=True),
                "name": st.column_config.TextColumn("Stock Name", disabled=True),
                "quantity": st.column_config.NumberColumn("Quantity", min_value=0, step=1)
            },
            hide_index=True,
            key="portfolio_editor"
        )
        if st.session_state.get("portfolio_editor", {}).get("edited_rows") or \
           st.session_state.get("portfolio_editor", {}).get("added_rows") or \
           st.session_state.get("portfolio_editor", {}).get("deleted_rows"):
            save_portfolio_changes(db_path, edited_df)
            st.success("Portfolio changes saved!")
    else:
        st.write("No stocks in portfolio yet. Add one above!")

# 說明
st.info("""
This is Taiwan Stock Tracker V1.0! Enter a stock code (e.g., 2330) or name (e.g., Taiwan Semiconductor) to see prices and charts.
Manage your portfolio by adding, editing, or deleting stocks with quantities.
Data is stored in a database at the specified path (default: stock_data.db).
For real-time data, consider paid APIs like TWSE or Finnhub.
To run locally: pip install streamlit yfinance plotly pandas ta fuzzywuzzy python-levenshtein; streamlit run app.py.
""")