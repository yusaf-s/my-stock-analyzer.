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

# 2. Sidebar - Updated with 1 Hour option
symbol = st.sidebar.text_input("Ticker", "silverline.BO")
# Added "1h" to the selection
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1h", "1mo", "1y"], index=0)

# 3. Data Engine
def get_live_data(ticker, pd_val):
    # Mapping intervals correctly: 1h horizon usually uses 1m or 2m bars for detail
    interval_map = {"1d": "1m", "5d": "5m", "1h": "1m", "1mo": "1d", "1y": "1d"}
    try:
        # For the 1h horizon, we technically fetch 1d of data but will filter it in the display
        fetch_period = "1d" if pd_val == "1h" else pd_val
        data = yf.download(ticker, period=fetch_period, interval=interval_map[pd_val], progress=False)
        
        # Fallback if data is thin
        if data is None or len(data) < 5:
            data = yf.download(ticker, period="4d", interval="1m", progress=False)
            if not data.empty:
                last_date = data.index[-1].date()
                data = data[data.index.date == last_date]
        
        if data.empty: return None
        
        # Handle MultiIndex Columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        # If user selected 1h horizon, filter for only the last 60 minutes
        if pd_val == "1h":
            data = data.tail(60)
            
        return data
    except: return None

df = get_live_data(symbol, period)

if df is None or len(df) < 10:
    st.error("❌ Waiting for market data... Retrying soon.")
    time.sleep(5)
    st.rerun()
else:
    # --- 4. CALCULATIONS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)

    epsilon = 0.00001
    df['Range'] = (df['High'] - df['Low']) + epsilon
    df['Buy_Vol'] = df['Volume'] * (df['Close'] - df['Low']) / df['Range']
    df['Sell_Vol'] = df['Volume'] * (df['High'] - df['Close']) / df['Range']
    
    # Current (Last Candle)
    current_buy_vol = float(df['Buy_Vol'].iloc[-1])
    current_sell_vol = float(df['Sell_Vol'].iloc[-1])
    
    # Period Totals
    total_period_buy = df['Buy_Vol'].sum()
    total_period_sell = df['Sell_Vol'].sum()
    total_period_vol = total_period_buy + total_period_sell
    
    # Percentage for Sentiment Bar
    buy_pct_total = (total_period_buy / total_period_vol * 100) if total_period_vol > 0 else 50
    sell_pct_total = 100 - buy_pct_total

    # --- TARGET LOGIC ---
    last_close = float(df['Close'].iloc[-1])
    recent_prices = df['Close'].tail(15).dropna().values.flatten().astype(float)
    
    if len(recent_prices) > 5:
        x_vals = np.arange(len(recent_prices))
        slope, intercept = np.polyfit(x_vals, recent_prices, 1)
        raw_prediction = slope * (len(recent_prices) + 2) + intercept 
        prediction = np.clip(raw_prediction, last_close * 0.95, last_close * 1.05)
    else:
        prediction = last_close

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[df.index[-1]], y=[prediction],
        mode='markers+text',
        text=[f"  Target: ₹{prediction:.2f}"],
        textposition="middle right",
        marker=dict(symbol='star', size=18, color="yellow", line=dict(width=1, color="white")),
        name='Target'
    ), row=1, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df['Buy_Vol'], name='Buy Vol', marker_color='#26a69a'), row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Sell_Vol'], name='Sell Vol', marker_color='#ef5350'), row=2, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2), name='RSI'), row=3, col=1)
    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, barmode='stack', showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. VISUAL VOLUME BAR (TUG OF WAR) ---
    st.markdown(f"### 📊 Cumulative Sentiment Bar ({period})")
    
    bar_html = f"""
    <div style="width: 100%; background-color: #444; border-radius: 8px; display: flex; height: 35px; overflow: hidden; border: 1px solid #555;">
        <div style="width: {buy_pct_total}%; background-color: #26a69a; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
            {buy_pct_total:.1f}% BUY
        </div>
        <div style="width: {sell_pct_total}%; background-color: #ef5350; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
            {sell_pct_total:.1f}% SELL
        </div>
    </div>
    """
    st.markdown(bar_html, unsafe_allow_html=True)
    st.markdown("---")

    # --- 7. DASHBOARD METRICS ---
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.metric("Live Price", f"₹{last_close:.2f}")
        change_pct = ((prediction / last_close) - 1) * 100
        st.metric("Target Price", f"₹{prediction:.2f}", f"{change_pct:+.2f}%")

    with c2:
        st.metric("Period Buy Vol", f"{total_period_buy:,.0f}")
        st.caption(f"Last Candle: {current_buy_vol:,.0f}")
        
    with c3:
        st.metric("Period Sell Vol", f"-{total_period_sell:,.0f}", delta_color="inverse")
        st.caption(f"Last Candle: {current_sell_vol:,.0f}")
        
    with c4:
        st.write("**Total Period Vol**")
        st.subheader(f"{total_period_vol:,.0f}")
        
        # RSI Safety Check to prevent crashes
        rsi_val = df['RSI'].iloc[-1]
        rsi_text = f"{rsi_val:.1f}" if not np.isnan(rsi_val) else "Wait..."
        st.info(f"RSI: {rsi_text}")

    # --- 8. COUNTDOWN ---
    for i in range(refresh_rate, -1, -1):
        timer_placeholder.markdown(f"⏳ **Next Refresh in:** `{i}s`")
        time.sleep(1)
        
    st.rerun()
