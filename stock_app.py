import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz

st.set_page_config(layout="wide", page_title="India Alpha: Ultimate Predictor")

# 1. Header & Time
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
st.title("🚀 India Alpha: Trend Predictor")
st.write(f"🕒 **Market Time:** {current_time}")

# 2. Inputs
symbol = st.sidebar.text_input("Ticker", "500389.BO")
period = st.sidebar.selectbox("Horizon", ["1mo", "1y", "5y"], index=0)

# 3. Data Engine
@st.cache_data
def get_data(ticker, pd_val):
    try:
        data = yf.download(ticker, period=pd_val, interval="1d")
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except: return None

df = get_data(symbol, period)

if df is None or len(df) < 20:
    st.error("❌ Need more data for prediction. Please select '1mo' or '1y'.")
else:
    # --- INDICATORS & PREDICTION ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=15)
    
    # Simple Trend Prediction (Linear Regression on last 10 days)
    y = df['Close'].tail(10).values
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    prediction = slope * (len(y) + 1) + intercept
    trend_direction = "UP 📈" if slope > 0 else "DOWN 📉"

    # Support/Resistance
    last_h, last_l, last_c = df['High'].iloc[-2], df['Low'].iloc[-2], df['Close'].iloc[-2]
    pivot = (last_h + last_l + last_c) / 3
    res = (2 * pivot) - last_l
    sup = (2 * pivot) - last_h

    # Signals
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    df = pd.concat([df, bb], axis=1).copy()
    l_band = df.filter(like='BBL').iloc[:,0]
    u_band = df.filter(like='BBU').iloc[:,0]
    df['Buy_S'] = (df['Close'] <= l_band) & (df['RSI'] < 45)
    df['Sell_S'] = (df['Close'] >= u_band) & (df['RSI'] > 55)

    # --- CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # Support/Resistance Lines
    fig.add_hline(y=res, line_dash="dot", line_color="red", annotation_text="RES", row=1, col=1)
    fig.add_hline(y=sup, line_dash="dot", line_color="lime", annotation_text="SUP", row=1, col=1)

    # Prediction Target Marker
    fig.add_trace(go.Scatter(x=[df.index[-1]], y=[prediction], mode='markers', marker=dict(symbol='star', size=15, color='yellow'), name='Tomorrow Target'), row=1, col=1)

    # Signals
    buy_pts = df[df['Buy_S']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.98, mode='markers+text', text="BUY", textfont=dict(color="lime"), marker=dict(symbol='triangle-up', color='lime'), name='BUY'), row=1, col=1)

    # Volume & RSI
    colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta')), row=3, col=1)

    fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use
