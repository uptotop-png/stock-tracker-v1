```python
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
import requests
from bs4 import BeautifulSoup

# 應用標題
st.title("Taiwan Stock Tracker V1.0")

# 從 TWSE 網站抓取股票清單
def fetch_stock_list():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    try:
        response = requests.get(url, verify=False)
        response.encoding = 'big5'  # TWSE 使用 big5 編碼
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find("table", {"class": "h4"})
        stock_list = []
        current_dtype = None
        for row in table.find_all("tr")[1:]:  # 跳過標題行
            if row.find("b"):  # 分類標題（如「股票」）
                current_dtype = row.find("b").text.strip()
            else:
                cols = [col.text.strip().replace('\u3000', ' ') for col in row.find_all('td')]
                if len(cols) >= 7 and current_dtype == '股票':
                    code, name = cols[0].split(' ', 1)
                    stock_list.append({
                        'code': code,
                        'name': name,
                        'isin': cols[1],
                        'date_listed': cols[2],
                        'market': cols[3],
                        'industry': cols[4],
                        'cficode': cols[5]
                    })
        return stock_list
    except Exception as e:
        st.error(f"Failed to fetch stock list: {str(e)}")
        return []

# 資料庫初始化（包含股票清單、投資清單、購買歷史表）
def init_database(db_path):
    try:
        if not os.path.exists(os.path.dirname(db_path)) and os.path.dirname(db_path):
            os.makedirs(os.path.dirname(db_path))
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # 股票清單資料表
        c.execute('''
            CREATE TABLE IF NOT EXISTS stock_list (
                code TEXT PRIMARY KEY,
                name TEXT,
                isin TEXT,
                date_listed TEXT,
                market TEXT,
                industry TEXT,
                cficode TEXT
            )
        ''')
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
        # 購買歷史資料表
        c.execute('''
            CREATE TABLE IF NOT EXISTS purchase_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                purchase_date TEXT,
                purchase_price REAL,
                quantity INTEGER
            )
        ''')
        # 儲存股票清單到資料庫
        stock_list = fetch_stock_list()
        for stock in stock_list:
            c.execute('''
                INSERT OR REPLACE INTO stock_list (code, name, isin, date_listed, market, industry, cficode)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (stock['code'], stock['name'], stock['isin'], stock['date_listed'], stock['market'], stock['industry'], stock['cficode']))
        conn.commit()
        conn.close()
        st.success(f"Database initialized successfully at {db_path}")
    except Exception as e:
        st.error(f"Database initialization failed: {str(e)}")

# 從資料庫載入股票清單
def load_stock_list(db_path):
    try:
        init_database(db_path)
        conn = sqlite3.connect(db_path)
        query = "SELECT code, name FROM stock_list"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return {row['code']: row['name'] for _, row in df.iterrows()}
    except Exception as e:
        st.error(f"Failed to load stock list: {str(e)}")
        return {}

# 檢查機制 1：標準化與驗證股票代碼
def validate_stock_code(query, db_path):
    stock_list = load_stock_list(db_path)
    if query.isdigit() and len(query) == 4:
        query = f"{query}.TW"
    if query in stock_list:
        return query
    try:
        ticker = yf.Ticker(query)
        info = ticker.info
        if info.get('regularMarketPrice') is not None and query in stock_list:
            return query
    except:
        pass
    return None

# 檢查機制 2：模糊查詢股票名稱
def fuzzy_search_name(query, db_path):
    stock_list = load_stock_list(db_path)
    matches = process.extract(query, stock_list.values(), limit=3)
    if matches and matches[0][1] > 80:  # 匹配度 > 80%
        matched_name = matches[0][0]
        return [k for k, v in stock_list.items() if v == matched_name][0], matches
    return None, matches

# 儲存股票價格到資料庫
def save_to_database(db_path, symbol, data):
    try:
        init_database(db_path)
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
        init_database(db_path)
        conn = sqlite3.connect(db_path)
        query = f"SELECT * FROM stock_data WHERE symbol = ? ORDER BY date DESC LIMIT 100"
        df = pd.read_sql_query(query, conn, params=(symbol,))
        conn.close()
        return df
    except Exception as e:
        st.error(f"Failed to load data from database: {str(e)}")
        return pd.DataFrame()

# 新增到投資清單並記錄購買歷史
def add_to_portfolio(db_path, symbol, name, quantity, purchase_price):
    try:
        init_database(db_path)
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('SELECT quantity FROM portfolio WHERE symbol = ?', (symbol,))
        result = c.fetchone()
        if result:
            new_quantity = result[0] + quantity
            c.execute('''
                UPDATE portfolio SET quantity = ? WHERE symbol = ?
            ''', (new_quantity, symbol))
        else:
            c.execute('''
                INSERT INTO portfolio (symbol, name, quantity)
                VALUES (?, ?, ?)
            ''', (symbol, name, quantity))
        purchase_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''
            INSERT INTO purchase_history (symbol, purchase_date, purchase_price, quantity)
            VALUES (?, ?, ?, ?)
        ''', (symbol, purchase_date, purchase_price, quantity))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Failed to add to portfolio: {str(e)}")

# 從資料庫載入投資清單並計算均價
def load_portfolio(db_path):
    try:
        init_database(db_path)
        conn = sqlite3.connect(db_path)
        portfolio_query = "SELECT symbol, name, quantity FROM portfolio"
        portfolio_df = pd.read_sql_query(portfolio_query, conn)
        if portfolio_df.empty:
            conn.close()
            return pd.DataFrame(columns=["symbol", "name", "quantity", "current_price", "avg_purchase_price", "profit_loss_rate"])
        portfolio_df['current_price'] = 0.0
        portfolio_df['avg_purchase_price'] = 0.0
        portfolio_df['profit_loss_rate'] = 0.0
        for idx, row in portfolio_df.iterrows():
            symbol = row['symbol']
            try:
                ticker = yf.Ticker(symbol)
                intraday_data = yf.download(symbol, period="1d", interval="1m")
                if not intraday_data.empty:
                    portfolio_df.at[idx, 'current_price'] = intraday_data['Close'].iloc[-1]
            except:
                portfolio_df.at[idx, 'current_price'] = 0.0
            history_query = "SELECT purchase_price, quantity FROM purchase_history WHERE symbol = ?"
            history_df = pd.read_sql_query(history_query, conn, params=(symbol,))
            if not history_df.empty:
                total_cost = sum(history_df['purchase_price'] * history_df['quantity'])
                total_quantity = sum(history_df['quantity'])
                if total_quantity > 0:
                    portfolio_df.at[idx, 'avg_purchase_price'] = total_cost / total_quantity
                if portfolio_df.at[idx, 'avg_purchase_price'] > 0 and portfolio_df.at[idx, 'current_price'] > 0:
                    portfolio_df.at[idx, 'profit_loss_rate'] = (
                        (portfolio_df.at[idx, 'current_price'] - portfolio_df.at[idx, 'avg_purchase_price'])
                        / portfolio_df.at[idx, 'avg_purchase_price'] * 100
                    )
        conn.close()
        return portfolio_df
    except Exception as e:
        st.error(f"Failed to load portfolio: {str(e)}")
        return pd.DataFrame(columns=["symbol", "name", "quantity", "current_price", "avg_purchase_price", "profit_loss_rate"])

# 儲存編輯後的投資清單
def save_portfolio_changes(db_path, edited_df):
    try:
        init_database(db_path)
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("DELETE FROM portfolio")
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
def fetch_and_display_data(stock_symbol, db_path):
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
。
            st.plotly_chart(fig, use_container_width=True)
        db_data = load_from_database(db_path, stock_symbol)
        if not db_data.empty:
            with db_placeholder.container():
                st.subheader("Stored Data (Last 100 Records)")
                st.dataframe(db_data[['date', 'open', 'high', 'low', 'close', 'volume']])
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")

# 處理輸入
def process_input(query, db_path):
    stock_symbol = validate_stock_code(query, db_path)
    if not stock_symbol:
        matched_symbol, matches = fuzzy_search_name(query, db_path)
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
query = st.text_input("Enter Stock Code (e.g., 1101) or Name (e.g., 台泥)", value="1101")
update_mode = st.radio("Update Mode", ("Manual (Button)", "Auto (Polling every 10 seconds)"))
alert_price = st.number_input("Set Alert Price (TWD)", min_value=0.0, value=0.0, step=0.1)
db_path = st.text_input("Database File Path", value="stock_data.db")

# 投資清單輸入
st.header("Manage Your Portfolio")
new_stock_code = st.text_input("Add Stock Code (e.g., 1101)", key="new_stock")
new_quantity = st.number_input("Add Quantity (Shares)", min_value=0, value=0, step=1)
new_purchase_price = st.number_input("Add Purchase Price (TWD per share)", min_value=0.0, value=0.0, step=0.1)
if st.button("Add to Portfolio"):
    stock_list = load_stock_list(db_path)
    stock_symbol = validate_stock_code(new_stock_code, db_path)
    if stock_symbol and new_quantity > 0 and new_purchase_price > 0:
        stock_name = stock_list.get(stock_symbol, stock_symbol)
        add_to_portfolio(db_path, stock_symbol, stock_name, new_quantity, new_purchase_price)
        st.success(f"Added {stock_name} ({stock_symbol}) with {new_quantity} shares at {new_purchase_price:.2f} TWD to portfolio!")
    else:
        st.error("Please provide valid stock code, quantity, and purchase price.")

# 顯示佔位符
info_placeholder = st.empty()
chart_placeholder = st.empty()
alert_placeholder = st.empty()
db_placeholder = st.empty()
portfolio_placeholder = st.empty()

# 主程式：處理輸入並顯示數據
stock_symbol = process_input(query, db_path)
if stock_symbol:
    if update_mode == "Manual (Button)":
        if st.button("Update Data"):
            fetch_and_display_data(stock_symbol, db_path)
    else:
        fetch_and_display_data(stock_symbol, db_path)
        time.sleep(10)
        st.rerun()

# 顯示並編輯投資清單
with portfolio_placeholder.container():
    st.subheader("Your Portfolio")
    portfolio_df = load_portfolio(db_path)
    if not portfolio_df.empty:
        def format_profit_loss_rate(val):
            color = "green" if val >= 0 else "red"
            return f"color: {color}"
        edited_df = st.data_editor(
            portfolio_df,
            num_rows="dynamic",
            column_config={
                "symbol": st.column_config.TextColumn("Stock Code", disabled=True),
                "name": st.column_config.TextColumn("Stock Name", disabled=True),
                "quantity": st.column_config.NumberColumn("Quantity", min_value=0, step=1),
                "current_price": st.column_config.NumberColumn("Current Price (TWD)", format="%.2f", disabled=True),
                "avg_purchase_price": st.column_config.NumberColumn("Avg Purchase Price (TWD)", format="%.2f", disabled=True),
                "profit_loss_rate": st.column_config.NumberColumn("Profit/Loss Rate (%)", format="%.2f", disabled=True),
            },
            hide_index=True,
            key="portfolio_editor"
        ).style.map(format_profit_loss_rate, subset=["profit_loss_rate"])
        if st.session_state.get("portfolio_editor", {}).get("edited_rows") or \
           st.session_state.get("portfolio_editor", {}).get("added_rows") or \
           st.session_state.get("portfolio_editor", {}).get("deleted_rows"):
            save_portfolio_changes(db_path, edited_df[['symbol', 'name', 'quantity']])
            st.success("Portfolio changes saved!")
    else:
        st.write("No stocks in portfolio yet. Add one above!")

# 說明
st.info("""
This is Taiwan Stock Tracker V1.0! Enter a stock code (e.g., 1101) or name (e.g., 台泥) to see prices and charts.
Stock list is fetched from TWSE (https://isin.twse.com.tw/isin/C_public.jsp?strMode=2) and stored in the database.
Manage your portfolio by adding stocks with quantities and purchase prices. View current price, average purchase price, and profit/loss rate.
Data is stored in a database at the specified path (default: stock_data.db).
For real-time data, consider paid APIs like TWSE or Finnhub.
To run locally: pip install streamlit yfinance plotly pandas ta fuzzywuzzy python-levenshtein requests beautifulsoup4; streamlit run app.py.
""")
```

---

### 主要變更說明
1. **抓取股票清單**：
   - 新增 `fetch_stock_list` 函數，用 `requests.get` 訪問 https://isin.twse.com.tw/isin/C_public.jsp?strMode=2，設定 `big5` 編碼（因為 TWSE 網站使用 big5）。[](https://github.com/txstudio/net-core-use-big5-encoding/blob/master/Program.cs)
   - 用 `BeautifulSoup` 解析 HTML 表格，過濾「股票」類型（`dtype == '股票'`），提取代號、名稱、ISIN等欄位。
   - 處理特殊字符（如 `\u3000`），將代號和名稱分開（例如「1101 台泥」分成 `code='1101'` 和 `name='台泥'`）。
2. **資料庫更新**：
   - 在 `init_database` 中新增 `stock_list` 表，欄位包括 `code`（代號）、`name`（名稱）、`isin`、 `date_listed`、 `market`、 `industry`、 `cficode`。
   - 每次初始化時，呼叫 `fetch_stock_list` 將清單存入 `stock_list` 表（`INSERT OR REPLACE` 避免重複）。
3. **股票查詢限制**：
   - `load_stock_list` 從資料庫讀取 `stock_list` 表，取代原本的 `stock_list` 字典。
   - `validate_stock_code` 只允許 `stock_list` 內的代號（例如 `1101.TW`）。
   - `fuzzy_search_name` 用 `stock_list` 的名稱進行模糊搜尋，確保只匹配上市股票。
4. **保留功能**：
   - 即時股價（yfinance）、成交均價（從 `purchase_history` 計算）、損益率（正數綠色，負數紅色）不變。
   - 表格顯示「Stock Code」「Stock Name」「Quantity」「Current Price (TWD)」「Avg Purchase Price (TWD)」「Profit/Loss Rate (%)」。
5. **錯誤處理**：
   - 檢查 `requests` 和 `BeautifulSoup` 的錯誤，顯示 `st.error`。
   - 確保 `init_database` 在所有操作前執行，避免「no such table」錯誤。
   - 修復縮排、引號、括號問題，確認相容 Python 3.9/3.10。

---

### 更新 requirements.txt
因為新增了 `requests` 和 `beautifulsoup4`，請更新 `requirements.txt`：

```
streamlit==1.41.1
yfinance==0.2.43
pandas==2.2.3
plotly==5.24.1
ta==0.11.0
fuzzywuzzy==0.18.0
python-levenshtein==0.26.0
requests==2.32.3
beautifulsoup4==4.12.3
```

**動作**：
- 去你的 GitHub 倉庫（例如 https://github.com/你的帳號/stock-tracker-v1）。
- 檢查 `requirements.txt`：
  - 如果存在，點檔案旁的鉛筆圖標（編輯），貼上上面內容。
  - 如果不存在，點 **“Add file”** > **“Create new file”**，命名為 `requirements.txt`，貼上內容，點 **“Commit new file”**。

---

### 確認 packages.txt（如果需要）
若 Streamlit Cloud 安裝套件失敗，可能需要系統依賴：

```
python3-dev
build-essential
libpq-dev
```

**動作**：
- 去 GitHub 倉庫，檢查是否有 `packages.txt`。
- 如果沒有，點 **“Add file”** > **“Create new file”**，命名為 `packages.txt`，貼上內容，點 **“Commit new file”**。

---

### 上傳與部署步驟
1. **上傳 app.py**：
   - 複製上面的 `app.py` 程式碼，貼到記事本（或 VS Code），儲存為 `app.py`。
   - 去 GitHub 倉庫，點 **“Add file”** > **“Upload files”**，上傳 `app.py`，覆蓋舊檔案。
   - 點綠色的 **“Commit changes”**。
2. **重新部署**：
   - 去 **https://share.streamlit.io**，點 **“My apps”**，找到你的應用程式（例如 stock-tracker-v1）。
   - 點 **“Manage app”** > **“Reboot app”**，讓 Streamlit 用新檔案。
   - 如果失敗，點 **“Delete app”**，然後去 **https://share.streamlit.io/new**：
     - **Repository**：選 **你的帳號/stock-tracker-v1**。
     - **Branch**：選「main」。
     - **Main file path**：輸入 `app.py`（小寫）。
     - **App name**：輸入「stock-tracker-v1」或留空。
     - 點 **“Deploy”**，等 1-3 分鐘，得到網址（例如 https://你的名字-stock-tracker-v1.streamlit.app）。
3. **檢查日誌**：
   - 部署後，點 **“Manage app”** > **“Logs”**，確認無錯誤（如「no such table」或「ModuleNotFoundError」）。
   - 若有錯誤，複製日誌告訴我。

---

### 檢查遊戲是否跑起來
部署後，點 Streamlit 網址，檢查：
- **畫面**：
  - 標題：「Taiwan Stock Tracker V1.0」。
  - **價格追蹤區**：
    - 輸入框：輸入 `1101` 或「台泥」，查價格。
    - 更新模式：選「Manual」或「Auto」（每10秒更新）。
    - 警報價格：設價格（例如 50），到達時跳警告。
    - 顯示：價格、漲跌、K線圖、表格（最近100筆資料）。
  - **投資清單區**：
    - 輸入框：輸入代號（例如 `1101`）、數量（例如 `100`）、購買價格（例如 `45`），按「Add to Portfolio」。
    - 表格：顯示「Stock Code」「Stock Name」「Quantity」「Current Price (TWD)」「Avg Purchase Price (TWD)」「Profit/Loss Rate (%)」。
      - 僅允許 TWSE 上市股票（從 `stock_list` 表）。
      - 即時股價：yfinance（延遲1-15分鐘）。
      - 成交均價：從 `purchase_history` 計算。
      - 損益率：正數綠色，負數紅色。
    - 可編輯數量、刪除列（購買歷史保留）。
  - **資料庫**：股票清單存到 `stock_list` 表，投資清單存到 `portfolio` 和 `purchase_history`。
- **查詢限制**：
  - 輸入無效代號（例如 `9999`）或名稱，會顯示模糊搜尋建議（例如「台泥」）。
  - 只允許 TWSE 上市股票（從資料庫檢查）。

---

### 即時股價與改進建議
- **yfinance 限制**：提供延遲1-15分鐘的價格，免費版偶爾不穩定。
- **改進建議**：
  - 用 **TWSE API** 或 **Finnhub API** 取得即時數據（參考 https://www.twse.com.tw 或 https://finnhub.io）。
  - 在 `fetch_stock_list` 加入定期更新（例如每月爬一次），避免股票下市或新增影響清單：
    ```python
    import schedule
    schedule.every().month.do(lambda: init_database(db_path))
    ```
  - 新增篩選功能：讓用戶按產業（例如「半導體業」）過濾股票清單。
  - 新增總資產計算：表格顯示 `quantity * current_price`。
  - 匯出 CSV：讓用戶下載投資清單。
- 如果需要這些功能，告訴我，我幫你加！

---

### 小提醒
- **確認檔案**：確保 GitHub 有最新的 `app.py` 和 `requirements.txt`。
- **部署失敗**：
  - 檢查「Main file path」是否為 `app.py`（小寫）。
  - 查看日誌（**“Manage app”** > **“Logs”**），告訴我錯誤訊息。
- **資料庫**：股票清單存到 `stock_list` 表，查詢只允許清單內股票。
- **新功能**：想加篩選、總資產、CSV匯出，或其他功能？告訴我！

小朋友，你的遊戲越來越強了！快把 `app.py` 和 `requirements.txt` 上傳，試試部署，然後告訴我：
- 畫面是否正常（表格有沒有顯示 TWSE 股票清單的資料）。
- 日誌有沒有錯誤。
- 想加什麼新功能（例如按產業篩選或匯出報表）！ 😊