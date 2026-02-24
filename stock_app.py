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

# --- AUTO-REFRESH CONFIG ---
refresh_rate = 30

# 1. Header & IST Setup
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
st.title("🚀 India Alpha: Silverline Ultimate Tracker")

timer_placeholder = st.empty()
st.write(f"🕒 **Last Update (IST):** {current_time}")

# 2. Sidebar - Added 1h, 15m, and 4h
symbol = st.sidebar.text_input("Ticker", "silverline.BO")
period_choice = st.sidebar.selectbox("Horizon", ["1h", "15m", "1d", "4h", "5d", "1mo", "1y"], index=0)

# 3. Data Engine
def get_live_data(ticker, pd_val):
    # Mapping logic for various timeframes
    # (Fetch Period, Interval)
    mapping = {
        "15m": ("1d", "1m"),
        "1h":  ("1d", "1m"),
        "1d":  ("1d", "1m"),
        "4h":  ("5d", "30m"),
        "5d":  ("5d", "5m"),
        "1mo": ("1mo", "1d"),
        "1y":  ("1y", "1d")
    }
    
    p, i = mapping[pd_val]
    
    try:
        data = yf.download(ticker, period=p, interval=i, progress=False)
        
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        # --- STRICT TIME SLICING ---
        if pd_val == "1h":
            data = data.tail(60) # Last 60 minutes
        elif pd_val == "15m":
            data = data.tail(15) # Last 15 minutes
        elif pd_val == "4h":
            data = data.tail(8)  # Last 8 candles of 30m = 4 hours
            
        return data
    except: return None

df = get_live_data(symbol, period_choice)

if df is None or len(df) < 5:
    st.error(f"❌ Waiting for {period_choice} data... Market might be closed or ticker invalid.")
    time.sleep(5)
    st.rerun()
else:
    # --- 4. CALCULATIONS ---
    # Use a shorter RSI length if the data slice is very small
    rsi_len = 14 if len(df) > 14 else len(df) - 1
    df['RSI'] = ta.rsi(df['Close'], length=rsi_len) if rsi_len > 0 else 50
    
    epsilon = 0.00001
    df['Range'] = (df['High'] - df['Low']) + epsilon
    df['Buy_Vol'] = df['Volume'] * (df['Close'] - df['Low']) / df['Range']
    df['Sell_Vol'] = df['Volume'] * (df['High'] - df['Close']) / df['Range']
    
    # Current Metrics
    current_buy_vol = float(df['Buy_Vol'].iloc[-1])
    current_sell_vol = float(df['Sell_Vol'].iloc[-1])
    
    # Period Totals
    total_period_buy = df['Buy_Vol'].sum()
    total_period_sell = df['Sell_Vol'].sum()
    total_period_vol = total_period_buy + total_period_sell
    
    buy_pct_total = (total_period_buy / total_period_vol * 100) if total_period_vol > 0 else 50
    sell_pct_total = 100 - buy_pct_total

    # Target Logic
    last_close = float(df['Close'].iloc[-1])
    recent_prices = df['Close'].tail(15).dropna().values.flatten().astype(float)
    if len(recent_prices) > 2:
        x_vals = np.arange(len(recent_prices))
        slope, intercept = np.polyfit(x_vals, recent_prices, 1)
        raw_prediction = slope * (len(recent_prices) + 1) + intercept 
        prediction = np.clip(raw_prediction, last_close * 0.95, last_close * 1.05)
    else:
        prediction = last_close

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[df.index[-1]], y=[prediction], mode='markers+text',
        text=[f"  Target: ₹{prediction:.2f}"], textposition="middle right",
        marker=dict(symbol='star', size=18, color="yellow", line=dict(width=1, color="white")),
        name='Target'
    ), row=1, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df['Buy_Vol'], name='Buy Vol', marker_color='#26a69a'), row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Sell_Vol'], name='Sell Vol', marker_color='#ef5350'), row=2, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2), name='RSI'), row=3, col=1)
    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, barmode='stack', showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. VISUAL VOLUME BAR ---
    st.markdown(f"### 📊 Cumulative Sentiment Bar ({period_choice})")
    st.markdown(f"""
    <div style="width: 100%; background-color: #444; border-radius: 8px; display: flex; height: 35px; overflow: hidden; border: 1px solid #555;">
        <div style="width: {buy_pct_total}%; background-color: #26a69a; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
            {buy_pct_total:.1f}% BUY
        </div>
        <div style="width: {sell_pct_total}%; background-color: #ef5350; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
            {sell_pct_total:.1f}% SELL
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # --- 7. DASHBOARD METRICS ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Live Price", f"₹{last_close:.2f}")
        st.metric("Target Price", f"₹{prediction:.2f}", f"{((prediction/last_close)-1)*100:+.2f}%")
    with c2:
        st.metric("Period Buy Vol", f"{total_period_buy:,.0f}")
        st.caption(f"Last Candle: {current_buy_vol:,.0f}")
    with c3:
        st.metric("Period Sell Vol", f"-{total_period_sell:,.0f}", delta_color="inverse")
        st.caption(f"Last Candle: {current_sell_vol:,.0f}")
    with c4:
        st.write(f"**Total Period Vol ({period_choice})**")
        st.subheader(f"{total_period_vol:,.0f}")
        rsi_val = df['RSI'].iloc[-1]
        st.info(f"RSI: {rsi_val:.1f}" if not np.isnan(rsi_val) else "RSI: N/A")

    # --- 8. COUNTDOWN ---
    for i in range(refresh_rate, -1, -1):
        timer_placeholder.markdown(f"⏳ **Next Refresh in:** `{i}s`")
        time.sleep(1)
    st.rerun()
