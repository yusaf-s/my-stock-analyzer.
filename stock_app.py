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

# --- 1. CONFIG ---
st.set_page_config(layout="wide", page_title="India Alpha: Silverline Ultimate")
refresh_rate = 30
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Silverline Ultimate Tracker")
timer_placeholder = st.empty()
st.write(f"🕒 **Last Update (IST):** {current_time}")

# --- 2. SIDEBAR ---
symbol = st.sidebar.text_input("Ticker", "SILVERLINE.BO")
period_choice = st.sidebar.selectbox("Horizon", ["1h", "15m", "1d", "4h", "5d", "1mo", "1y"], index=0)
prediction_mode = st.sidebar.radio("Target Focus", ["Next Candle (Scalp)", "Next Day (Tomorrow)"])

# --- 3. DATA ENGINES ---
def get_live_data(ticker, pd_val):
    mapping = {
        "15m": ("1d", "1m"), "1h": ("1d", "1m"), "1d": ("1d", "1m"),
        "4h": ("5d", "30m"), "5d": ("5d", "5m"), "1mo": ("1mo", "1d"), "1y": ("1y", "1d")
    }
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

def get_volume_stats(ticker, label):
    # Mapping for fetching data
    if label == "4 Hour":
        # Aggregate 1h data into 4h
        data = yf.download(ticker, period="5d", interval="1h", progress=False)
    else:
        data = yf.download(ticker, period="1d", interval="1m", progress=False)
    
    if data.empty: return 0, 0
    if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
    
    # Slice the required amount of data
    counts = {"15 Mins": 15, "30 Mins": 30, "1 Hour": 60, "4 Hour": 4}
    df_sub = data.tail(counts[label]).copy()
    
    epsilon = 0.00001
    v_range = (df_sub['High'] - df_sub['Low']) + epsilon
    buy_v = df_sub['Volume'] * (df_sub['Close'] - df_sub['Low']) / v_range
    sell_v = df_sub['Volume'] * (df_sub['High'] - df_sub['Close']) / v_range
    return buy_v.sum(), sell_v.sum()

def predict_tomorrow(ticker):
    hist = yf.download(ticker, period="3mo", interval="1d", progress=False)
    if isinstance(hist.columns, pd.MultiIndex): hist.columns = hist.columns.get_level_values(0)
    closes = hist['Close'].dropna().values.astype(float)
    if len(closes) > 10:
        x = np.arange(len(closes))
        slope, intercept = np.polyfit(x, closes, 1)
        return slope * (len(closes) + 1) + intercept
    return None

# --- 4. EXECUTION ---
df = get_live_data(symbol, period_choice)

if df is None or len(df) < 2:
    st.error(f"❌ Waiting for data/Ticker not found...")
    time.sleep(5)
    st.rerun()
else:
    # --- 5. MULTI-TIMEFRAME VOLUME TABLE ---
    st.subheader("📊 Live Buy/Sell Volume Summary")
    vol_rows = []
    for tf_label in ["15 Mins", "30 Mins", "1 Hour", "4 Hour"]:
        b, s = get_volume_stats(symbol, tf_label)
        total = b + s
        buy_ratio = (b / total * 100) if total > 0 else 50
        sell_ratio = 100 - buy_ratio
        vol_rows.append({
            "Timeframe": tf_label,
            "Buy Volume": f"{b:,.0f}",
            "Sell Volume": f"{s:,.0f}",
            "Buy %": f"🟢 {buy_ratio:.1f}%",
            "Sell %": f"🔴 {sell_ratio:.1f}%",
            "Net Flow": f"{'✅' if b > s else '⚠️'} {(b-s):,.0f}"
        })
    st.table(pd.DataFrame(vol_rows))

    # --- 6. TARGETS & CHARTING ---
    last_close = float(df['Close'].iloc[-1])
    target_val = predict_tomorrow(symbol) if prediction_mode == "Next Day (Tomorrow)" else None
    if not target_val:
        recent = df['Close'].tail(15).dropna().values.astype(float)
        slope, intercept = np.polyfit(np.arange(len(recent)), recent, 1)
        target_val = slope * (len(recent) + 1) + intercept
    
    prediction = np.clip(target_val, last_close * 0.95, last_close * 1.05)
    
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray', opacity=0.3), row=2, col=1)
    
    rsi_len = 14 if len(df) > 14 else max(1, len(df)-1)
    df['RSI'] = ta.rsi(df['Close'], length=rsi_len)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2), name='RSI'), row=3, col=1)
    
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 7. FOOTER METRICS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Live Price", f"₹{last_close:.2f}")
    c2.metric("Target", f"₹{prediction:.2f}", f"{((prediction/last_close)-1)*100:+.2f}%")
    c3.info(f"RSI: {df['RSI'].iloc[-1]:.1f}")

    for i in range(refresh_rate, -1, -1):
        timer_placeholder.markdown(f"⏳ **Refresh in:** `{i}s`")
        time.sleep(1)
    st.rerun()
