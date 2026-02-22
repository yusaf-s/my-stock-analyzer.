import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz

st.set_page_config(layout="wide", page_title="India Alpha Analyzer")

# Header with Current Time
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Advanced Stock Analyzer")
st.write(f"🕒 **Current Market Time (IST):** {current_time}")

# 1. Inputs
symbol = st.sidebar.text_input("Ticker (NSE: .NS | BSE: .BO)", "SBIN.NS")
period = st.sidebar.selectbox("Analysis Horizon", ["1d", "5d", "1mo", "1y", "2y", "5y"], index=3)

# 2. Data Engine
@st.cache_data
def get_data(ticker, pd_val):
    intvl = "5m" if pd_val == "1d" else "30m" if pd_val == "5d" else "1d"
    try:
        data = yf.download(ticker, period=pd_val, interval=intvl)
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except: return None

df = get_data(symbol, period)

if df is None or len(df) < 20:
    st.error(f"❌ Not enough data for {symbol}. Try a longer horizon or a different ticker.")
else:
    # 3. Indicator Calculations
    df['RSI'] = ta.rsi(df['Close'], length=14)
    bb = ta.bbands(df['Close'], length=20, std=2)
    df = pd.concat([df, bb], axis=1).copy()
    
    # Identify Signal Points
    lower_band = df.filter(like='BBL').iloc[:,0]
    upper_band = df.filter(like='BBU').iloc[:,0]
    
    # Strategy: Buy when price < Lower Band and RSI < 35 | Sell when price > Upper Band and RSI > 65
    df['Buy_Signal'] = (df['Close'] < lower_band) & (df['RSI'] < 35)
    df['Sell_Signal'] = (df['Close'] > upper_band) & (df['RSI'] > 65)

    # 4. Charting
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3],
                        subplot_titles=('Price & Trade Signals', 'Volume', 'RSI'))

    # Candlestick
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # Plot BUY Labels + Arrows
    buy_points = df[df['Buy_Signal']]
    fig.add_trace(go.Scatter(
        x=buy_points.index, 
        y=buy_points['Low'] * 0.97, # Slightly below the low
        mode='markers+text',
        text="BUY",
        textposition="bottom center",
        marker=dict(symbol='triangle-up', size=12, color='lime'),
        textfont=dict(color="lime", size=14),
        name='BUY Signal'
    ), row=1, col=1)

    # Plot SELL Labels + Arrows
    sell_points = df[df['Sell_Signal']]
    fig.add_trace(go.Scatter(
        x=sell_points.index, 
        y=sell_points['High'] * 1.03, # Slightly above the high
        mode='markers+text',
        text="SELL",
        textposition="top center",
        marker=dict(symbol='triangle-down', size=12, color='red'),
        textfont=dict(color="red", size=14),
        name='SELL Signal'
    ), row=1, col=1)

    # Bollinger Bands
    fig.add_trace(go.Scatter(x=df.index, y=upper_band, line=dict(color='rgba(173, 216, 230, 0.2)'), name='Upper Band'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=lower_band, fill='tonexty', line=dict(color='rgba(173, 216, 230, 0.2)'), name='Lower Band'), row=1, col=1)

    # Volume & RSI
    colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict
