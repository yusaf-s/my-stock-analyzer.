import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- CONFIG ---
SYMBOL = "500389.BO"  # Silverline Technologies

st.set_page_config(layout="wide", page_title="Silverline Stable Pro")
st.title(f"📈 Silverline Tech (Stable View)")

def fetch_data():
    # Fetching 2 days to ensure we have enough points for technicals
    data = yf.download(SYMBOL, period="2d", interval="1m", progress=False)
    if data.empty:
        return None
    # Clean column names for new yfinance format
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

df = fetch_data()

if df is not None:
    # 1. Indicators
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # 2. FIXED TREND PREDICTION (The "Safe" Math)
    # We take the last 15 points, but verify we have at least 2 to draw a line
    points_to_fit = 15
    if len(df) > 2:
        y = df['Close'].tail(points_to_fit).values
        x = np.arange(len(y)) # This ensures x and y are ALWAYS the same length
        slope, intercept = np.polyfit(x, y, 1)
        prediction = slope * (len(y) + 5) + intercept
    else:
        prediction = df['Close'].iloc[-1]

    # 3. Signals
    df['Signal'] = "Hold"
    last_rsi = df['RSI'].iloc[-1]
    if last_rsi < 35: df['Signal'] = "BUY"
    if last_rsi > 75: df['Signal'] = "SELL"

    # 4. Professional Chart
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])

    # Candlestick
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    # Volume with Cyan Avg
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='orange'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='cyan', width=2), name='Vol Avg'), row=2, col=1)

    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # 5. Live Dashboard
    c1, c2, c3 = st.columns(3)
    c1.metric("Current", f"₹{df['Close'].iloc[-1]:.2f}")
    c2.metric("Trend Prediction", f"₹{prediction:.2f}")
    c3.metric("RSI (14)", f"{last_rsi:.1f}")

    if df['Signal'].iloc[-1] != "Hold":
        st.info(f"💡 Action: {df['Signal'].iloc[-1]}")

    time.sleep(30)
    st.rerun()
else:
    st.error("Market data unavailable. Please check your internet or Ticker symbol.")
    time.sleep(10)
    st.rerun()
