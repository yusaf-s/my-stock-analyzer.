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
st.set_page_config(layout="wide", page_title="India Alpha: Smart Market Analyzer")

# 1. Header & Time
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Smart Market Analyzer")
st.write(f"🕒 **Market Time (IST):** {current_time}")

# 2. Sidebar Inputs
symbol = st.sidebar.text_input("Ticker", "500389.BO")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y", "5y"], index=0)

# 3. Smart Data Engine (Handles Mondays/Weekends)
@st.cache_data
def get_data(ticker, pd_val):
    interval_map = {"1d": "1m", "5d": "15m", "1mo": "1d", "1y": "1d", "5y": "1d"}
    try:
        # Try fetching the requested period
        data = yf.download(ticker, period=pd_val, interval=interval_map[pd_val])
        
        # SMART LOGIC: If '1d' is selected but we have almost no data (Monday morning)
        if pd_val == "1d" and (data is None or len(data) < 15):
            # Fallback to '2d' to show the previous trading day's momentum
            data = yf.download(ticker, period="2d", interval="1m")
            st.info("💡 Limited data for today. Showing past 24 hours of market activity.")
            
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

df = get_data(symbol, period)

if df is None or len(df) < 10:
    st.error("❌ Market data currently unavailable. Please check the ticker symbol or try '5d'.")
else:
    # --- 4. INDICATORS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=15)
    
    # Trend Prediction
    lookback = min(len(df), 15)
    y_vals = df['Close'].tail(lookback).values
    x_vals = np.arange(len(y_vals))
    slope, intercept = np.polyfit(x_vals, y_vals, 1)
    prediction = slope * (len(y_vals) + 1) + intercept
    trend_dir = "UP 📈" if slope > 0 else "DOWN 📉"

    # Support/Resistance
    last_h, last_l, last_c = df['High'].iloc[-1], df['Low'].iloc[-1], df['Close'].iloc[-1]
    pivot = (last_h + last_l + last_c) / 3
    res_level = (2 * pivot) - last_l
    sup_level = (2 * pivot) - last_h

    # Bollinger Bands
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    df = pd.concat([df, bb], axis=1).copy()
    l_band = df.filter(like='BBL').iloc[:,0]
    u_band = df.filter(like='BBU').iloc[:,0]
    
    # Signal Logic
    df['Buy_S'] = (df['Close'] <= l_band) & (df['RSI'] < 45)
    df['Sell_S'] = (df['Close'] >= u_band) & (df['RSI'] > 55)

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=[df.index[-1]], y=[prediction], mode='markers', 
                             marker=dict(symbol='star', size=15, color='yellow'), name='Target'), row=1, col=1)

    fig.add_hline(y=res_level, line_dash="dot", line_color="red", annotation_text="RES", row=1, col=1)
    fig.add_hline(y=sup_level, line_dash="dot", line_color="lime", annotation_text="SUP", row=1, col=1)

    buy_pts = df[df['Buy_S']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.99, mode='markers+text', 
                             text="BUY", textfont=dict(color="lime"), 
                             marker=dict(symbol='triangle-up', color='lime'), name='BUY'), row=1, col=1)

    vol_colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta')), row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. DASHBOARD ---
    st.subheader(f"Analysis: {symbol}")
    c1, c2, c3 = st.columns(3)
    
    last_row = df.iloc[-1]
    
    c1.metric("Trend", trend_dir)
    c2.metric("Target", f"₹{prediction:.2f}")
    c3.metric("RSI", f"{last_row['RSI']:.1f}")
    
    is_high_vol = last_row['Volume'] > last_row['Vol_SMA']
    conf_text = "HIGH CONFIDENCE" if is_high_vol else "WEAK/FAKING"
    
    if last_row['Buy_S']:
        st.success(f"🚀 SIGNAL: BUY | Strength: {conf_text}")
    elif last_row['Sell_S']:
        st.error(f"⚠️ SIGNAL: SELL | Strength: {conf_text}")
    else:
        st.info("⚖️ MARKET STATUS: NEUTRAL")

    st.divider()
    st.download_button("📥 Export CSV", df.to_csv().encode('utf-8'), f"{symbol}.csv", "text/csv")
