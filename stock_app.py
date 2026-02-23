import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- FIXED TICKER ---
SYMBOL = "500389.BO"

st.set_page_config(layout="wide", page_title="Silverline Stable Fix")
st.title(f"📈 Silverline Tech (Stable & Fixed)")

def fetch_data():
    # Fetching 2 days to ensure we have enough points for RSI (needs 14+)
    data = yf.download(SYMBOL, period="5d", interval="15m", progress=False)
    if data.empty or len(data) < 15:
        return None
    # Fix for new yfinance format
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

df = fetch_data()

if df is not None:
    # 1. Indicators
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # 2. Safety Trend Prediction
    y = df['Close'].tail(15).values
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    prediction = slope * (len(y) + 1) + intercept

    # 3. FIXED: Accessing Scalar Values for Logic
    # We use .iloc[-1] to get the last row, then .item() to get the pure number
    current_rsi = df['RSI'].iloc[-1]
    current_price = df['Close'].iloc[-1]
    
    # Check if price/rsi are valid numbers (not NaN)
    if np.isnan(current_rsi):
        current_rsi = 50.0 # Neutral fallback

    # 4. Professional Chart
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='orange'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='cyan', width=3)), row=2, col=1)
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # 5. FIXED ACTION LOGIC
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"₹{current_price:.2f}")
    c2.metric("Target Prediction", f"₹{prediction:.2f}")
    c3.metric("RSI (14)", f"{current_rsi:.1f}")

    # Simple If-Else that won't crash
    if current_rsi < 35:
        st.success("🟢 BUY SIGNAL: Stock is oversold.")
    elif current_rsi > 70:
        st.error("🔴 SELL SIGNAL: Stock is overbought.")
    else:
        st.info("⚪ NEUTRAL: No clear RSI signal.")

    time.sleep(30)
    st.rerun()
else:
    st.warning("Data is refreshing or stock is at Circuit Limit. Retrying...")
    time.sleep(10)
    st.rerun()
