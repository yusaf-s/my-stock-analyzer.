import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz

# --- APP CONFIG ---
st.set_page_config(layout="wide", page_title="India Alpha: 24/7 Analyzer")

# 1. Header & Time
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: 24/7 Market Analyzer")
st.write(f"🕒 **Current Time (IST):** {current_time}")

# 2. Sidebar Inputs
symbol = st.sidebar.text_input("Ticker", "500389.BO")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y", "5y"], index=0)

# 3. Smart Fallback Engine
@st.cache_data
def get_data(ticker, pd_val):
    interval_map = {"1d": "1m", "5d": "5m", "1mo": "1d", "1y": "1d", "5y": "1d"}
    try:
        # Initial attempt
        data = yf.download(ticker, period=pd_val, interval=interval_map[pd_val])
        
        # If 1d is empty (Weekend/Monday morning), go back to find last Friday
        if pd_val == "1d" and (data is None or len(data) < 5):
            # We try 4 days to safely cover Friday even on a Monday morning
            data = yf.download(ticker, period="4d", interval="1m")
            if not data.empty:
                # Filter for only the most recent actual trading day found in those 4 days
                last_session_date = data.index[-1].date()
                data = data[data.index.date == last_session_date]
                st.info(f"📊 Market Closed. Showing last active session: {last_session_date}")
        
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

df = get_data(symbol, period)

if df is None or len(df) < 5:
    st.error("❌ No market data found. Please check the ticker symbol (e.g., 500389.BO).")
else:
    # --- 4. INDICATORS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=15)
    
    # Prediction (on the last 15 minutes/days of the found data)
    lookback = min(len(df), 15)
    y_vals = df['Close'].tail(lookback).values
    x_vals = np.arange(len(y_vals))
    slope, _ = np.polyfit(x_vals, y_vals, 1)
    # Target for the next bar
    prediction = slope * (len(y_vals) + 1) + np.polyfit(x_vals, y_vals, 1)[1]
    trend_dir = "UP 📈" if slope > 0 else "DOWN 📉"

    # Support/Resistance
    last_h, last_l, last_c = df['High'].iloc[-1], df['Low'].iloc[-1], df['Close'].iloc[-1]
    pivot = (last_h + last_l + last_c) / 3
    res_level = (2 * pivot) - last_l
    sup_level = (2 * pivot) - last_h

    # Signals
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    df = pd.concat([df, bb], axis=1).copy()
    l_band = df.filter(like='BBL').iloc[:,0]
    u_band = df.filter(like='BBU').iloc[:,0]
    df['Buy_S'] = (df['Close'] <= l_band) & (df['RSI'] < 45)
    df['Sell_S'] = (df['Close'] >= u_band) & (df['RSI'] > 55)

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # Resistance/Support
    fig.add_hline(y=res_level, line_dash="dot", line_color="red", annotation_text="RES", row=1, col=1)
    fig.add_hline(y=sup_level, line_dash="dot", line_color="lime", annotation_text="SUP", row=1, col=1)

    # Buy/Sell Markers
    buy_pts = df[df['Buy_S']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.995, mode='markers+text', 
                             text="BUY", textfont=dict(color="lime"), 
                             marker=dict(symbol='triangle-up', color='lime'), name='BUY'), row=1, col=1)

    # Volume & RSI
    vol_colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta')), row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. DASHBOARD ---
    last_row = df.iloc[-1]
    c1, c2, c3 = st.columns(3)
    c1.metric("Trend", trend_dir)
    c2.metric("Predicted Target", f"₹{prediction:.2f}")
    c3.metric("Current RSI", f"{last_row['RSI']:.1f}")
    
    if last_row['Buy_S']:
        st.success(f"🚀 SIGNAL: BUY (Oversold on {df.index[-1].date()})")
    elif last_row['Sell_S']:
        st.error(f"⚠️ SIGNAL: SELL (Overbought on {df.index[-1].date()})")
    else:
        st.info(f"⚖️ STATUS: NEUTRAL (Last Close: ₹{last_row['Close']:.2f})")

    st.divider()
    st.download_button("📥 Export CSV", df.to_csv().encode('utf-8'), f"{symbol}.csv", "text/csv")
    
