import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz
import time

# --- CONFIG ---
st.set_page_config(layout="wide", page_title="India Alpha: Silverline Ultimate")
refresh_rate = 30

# 1. Header & IST Setup
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
st.title("🚀 India Alpha: Silverline Ultimate + S&R Walls")

timer_placeholder = st.empty()
st.write(f"🕒 **Last Update (IST):** {current_time}")

# 2. Sidebar
symbol = st.sidebar.text_input("Ticker", "silverline.BO")
period_choice = st.sidebar.selectbox("Horizon", ["1h", "15m", "1d", "4h", "5d", "1mo", "1y"], index=0)
prediction_mode = st.sidebar.radio("Target Focus", ["Next Candle (Scalp)", "Next Day (Tomorrow)"])

# 3. Data Engine
def get_live_data(ticker, pd_val):
    mapping = {"15m": ("1d", "1m"), "1h": ("1d", "1m"), "1d": ("1d", "1m"), 
               "4h": ("5d", "30m"), "5d": ("5d", "5m"), "1mo": ("1mo", "1d"), "1y": ("1y", "1d")}
    p, i = mapping[pd_val]
    try:
        data = yf.download(ticker, period=p, interval=i, progress=False)
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        if pd_val == "1h": data = data.tail(60)
        elif pd_val == "15m": data = data.tail(15)
        elif pd_val == "4h": data = data.tail(8)
        return data
    except: return None

# 4. S&R Calculation (Standard Pivot Points)
def calc_pivot_levels(ticker):
    # Fetch previous day data for pivots
    hist = yf.download(ticker, period="2d", interval="1d", progress=False)
    if len(hist) < 2: return None
    if isinstance(hist.columns, pd.MultiIndex): hist.columns = hist.columns.get_level_values(0)
    
    prev_day = hist.iloc[-2]
    high, low, close = prev_day['High'], prev_day['Low'], prev_day['Close']
    
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    return {"PP": pivot, "R1": r1, "S1": s1}

df = get_live_data(symbol, period_choice)
sr_levels = calc_pivot_levels(symbol)

if df is not None:
    # --- 5. CALCULATIONS ---
    rsi_len = 14 if len(df) > 14 else max(1, len(df) - 1)
    df['RSI'] = ta.rsi(df['Close'], length=rsi_len)
    
    # Prediction Logic
    last_close = float(df['Close'].iloc[-1])
    recent_prices = df['Close'].tail(15).dropna().values.astype(float)
    x_vals = np.arange(len(recent_prices))
    slope, intercept = np.polyfit(x_vals, recent_prices, 1)
    target_val = slope * (len(recent_prices) + (1 if prediction_mode == "Next Candle (Scalp)" else 5)) + intercept
    prediction = np.clip(target_val, last_close * 0.90, last_close * 1.10)

    # --- 6. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    # Add S&R Lines
    if sr_levels:
        fig.add_hline(y=sr_levels['R1'], line_dash="dash", line_color="red", annotation_text="Resistance (R1)", row=1, col=1)
        fig.add_hline(y=sr_levels['S1'], line_dash="dash", line_color="green", annotation_text="Support (S1)", row=1, col=1)

    # Target Marker
    fig.add_trace(go.Scatter(x=[df.index[-1]], y=[prediction], mode='markers+text', 
                             text=[f" Target: ₹{prediction:.2f}"], textposition="middle right",
                             marker=dict(symbol='star', size=15, color="gold")), row=1, col=1)

    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Current", f"₹{last_close:.2f}")
    c2.metric("Target", f"₹{prediction:.2f}", f"{((prediction/last_close)-1)*100:+.2f}%")
    if sr_levels:
        dist_to_r1 = ((sr_levels['R1'] / last_close) - 1) * 100
        c3.metric("Dist to R1", f"{dist_to_r1:.2f}%", delta_color="inverse")

    for i in range(refresh_rate, -1, -1):
        timer_placeholder.markdown(f"⏳ **Refreshing in:** `{i}s`")
        time.sleep(1)
    st.rerun()
