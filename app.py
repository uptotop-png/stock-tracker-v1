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

# 完整 TWSE 股票清單（從公開來源提取，符號 + 公司名稱）
stock_list = {
    '2330.TW': 'Taiwan Semiconductor Manufacturing Company Limited',
    '2317.TW': 'Hon Hai Precision Industry Co., Ltd.',
    '2454.TW': 'MediaTek Inc.',
    '2308.TW': 'Delta Electronics, Inc.',
    '2881.TW': 'Fubon Financial Holding Co., Ltd.',
    '2412.TW': 'Chunghwa Telecom Co., Ltd.',
    '2382.TW': 'Quanta Computer Inc.',
    '2882.TW': 'Cathay Financial Holding Co., Ltd.',
    '2882A.TW': 'Cathay Financial Holding Co., Ltd.',
    '2882B.TW': 'Cathay Financial Holding Co., Ltd.',
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
    '3653.TW': 'Jentech Precision Industrial Co., Ltd',
    '2890.TW': 'SinoPac Financial Holdings Company Limited',
    '3008.TW': 'LARGAN Precision Co.,Ltd',
    '1303.TW': 'Nan Ya Plastics Corporation',
    '2207.TW': 'Hotai Motor Co.,Ltd.',
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
    '3665.TW': 'Biz