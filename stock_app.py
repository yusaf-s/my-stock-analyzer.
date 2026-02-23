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

# --- AUTO-REFRESH (30 Seconds) ---
refresh_rate = 30

# 1. Header
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
st.title("🚀 India Alpha: Silverline Ultimate Tracker")
st.write(f"🕒 **Last Update (IST):** {current_time} | *Refreshing every {refresh_rate}s*")

# 2. Sidebar
symbol = st.sidebar.text_input("Ticker", "silverline.BO")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y"], index=0)

# 3. Data Engine
def get_live_data(ticker, pd_val):
    interval_map = {"1d": "1m", "5d": "5m", "1mo": "1d", "1y": "1d"}
    try:
        data = yf.download(ticker, period=pd_val, interval=interval_map[pd_val], progress=False)
        if pd_val == "1d" and (data is None or len(data) < 5):
            data = yf.download(ticker, period="4d", interval="1m", progress=False)
            if not data.empty:
                last_date = data.index[-1].date()
                data = data[data.index.date == last_date]
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except: return None

df = get_live_data(symbol, period)

if df is None or len(df) < 15:
    st.error("❌ Waiting for market data... Retrying soon.")
else:
    # --- 4. CALCULATIONS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)

    # Prediction Logic with Market Constraints (5% Circuit)
    y_vals, x_vals = df['Close'].tail(10).values, np.arange(10)
    slope, intercept = np.polyfit(x_vals, y_vals, 1)
    
    # Mathematical Target
    raw_prediction = slope * 11 + intercept 
    
    # Circuit Limit Correction (Silverline is 5%)
    last_close = float(df['Close'].iloc[-1])
    upper_circuit = round(last_close * 1.05, 2)
    
    # Final Prediction: Use math but cap it at the legal circuit limit
    prediction = min(raw_prediction, upper_circuit)

    # Bollinger Bands & Signals
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    if bb is not None:
        df = pd.concat([df, bb], axis=1)
        l_col = [c for c in df.columns if 'BBL' in c][0]
        u_col = [c for c in df.columns if 'BBU' in c][0]
        df['Buy_S'] = (df['Close'] <= df[l_col]) & (df['RSI'] < 45)
        df['Sell_S'] = (df['Close'] >= df[u_col]) & (df['RSI'] > 55)

    # Aggregate volumes for signals
    buys = df[df['Buy_S']].copy()
    sells = df[df['Sell_S']].copy()
    total_buy_vol  = int(buys['Volume'].sum()) if not buys.empty else 0
    total_sell_vol = int(sells['Volume'].sum()) if not sells.empty else 0

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    # Prediction Star at Future Time
    last_time = df.index[-1]
    time_delta = df.index[-1] - df.index[-2]
    future_time = last_time + time_delta

    # Color Star Red if RSI is dangerously high (Fakeout Alert)
    last_rsi = df['RSI'].iloc[-1]
    star_color = "red" if last_rsi > 85 else "yellow"

    fig.add_trace(go.Scatter(
        x=[future_time], y=[prediction],
        mode='markers+text',
        text=[f"  Target: ₹{prediction:.2f}"],
        textposition="middle right",
        textfont=dict(color=star_color, size=12, family="Arial Black"),
        marker=dict(symbol='star', size=20, color=star_color, line=dict(width=2, color="white")),
        name='Predicted Next'
    ), row=1, col=1)

    # Volume & RSI
    vol_colors = ['#26a69a' if df['Open'].iloc[i] < df['Close'].iloc[i] else '#ef5350' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='Volume'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='cyan', width=2), name='Vol Avg'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. DASHBOARD ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Live Price", f"₹{last_close:.2f}")
        st.write(f"RSI: {last_rsi:.1f}")
    with c2:
        change = ((prediction / last_close) - 1) * 100
        st.metric("Target (Next Bar)", f"₹{prediction:.2f}", f"{change:.2f}%")
    with c3:
        if last_rsi > 85:
            st.warning("⚠️ FAKEOUT RISK: RSI EXTREME")
        else:
            st.success("✅ Momentum Stable")
    with c4:
        conf = "STRONG VOL" if df['Volume'].iloc[-1] > df['Vol_SMA'].iloc[-1] else "LOW VOL"
        st.info(f"Signal: {conf}")

    time.sleep(refresh_rate)
    st.rerun()
