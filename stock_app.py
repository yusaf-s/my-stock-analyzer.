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
symbol = st.sidebar.text_input("Ticker", "500389.BO")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y"], index=0)

# 3. Data Engine
def get_live_data(ticker, pd_val):
    interval_map = {"1d": "1m", "5d": "5m", "1mo": "1d", "1y": "1d"}
    try:
        data = yf.download(ticker, period=pd_val, interval=interval_map[pd_val], progress=False)
        # Fallback for Weekend/Monday morning
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
    
    # Prediction (10-bar regression)
    y_vals, x_vals = df['Close'].tail(10).values, np.arange(10)
    slope, intercept = np.polyfit(x_vals, y_vals, 1)
    prediction = slope * 11 + intercept

    # Bollinger Bands & Signals
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    if bb is not None:
        df = pd.concat([df, bb], axis=1)
        l_col = [c for c in df.columns if 'BBL' in c][0]
        u_col = [c for c in df.columns if 'BBU' in c][0]
        df['Buy_S'] = (df['Close'] <= df[l_col]) & (df['RSI'] < 45)
        df['Sell_S'] = (df['Close'] >= df[u_col]) & (df['RSI'] > 55)

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    # Main Price Chart
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    # ENHANCED BUY SIGNALS
    buys = df[df['Buy_S']].copy()
    if not buys.empty:
        # Check if High Confidence
        buys['label'] = buys.apply(lambda x: "STRONG BUY" if x['Volume'] > x['Vol_SMA'] else "BUY", axis=1)
        fig.add_trace(go.Scatter(x=buys.index, y=buys['Low']*0.99, mode='markers+text',
                                 text=buys['label'], textposition="bottom center",
                                 textfont=dict(color="lime", size=10),
                                 marker=dict(symbol='triangle-up', color='lime', size=22), name='BUY'), row=1, col=1)
    
    # ENHANCED SELL SIGNALS
    sells = df[df['Sell_S']].copy()
    if not sells.empty:
        sells['label'] = sells.apply(lambda x: "STRONG SELL" if x['Volume'] > x['Vol_SMA'] else "SELL", axis=1)
        fig.add_trace(go.Scatter(x=sells.index, y=sells['High']*1.01, mode='markers+text',
                                 text=sells['label'], textposition="top center",
                                 textfont=dict(color="red", size=10),
                                 marker=dict(symbol='triangle-down', color='red', size=22), name='SELL'), row=1, col=1)

    # Prediction Star
    fig.add_trace(go.Scatter(x=[df.index[-1]], y=[prediction], mode='markers',
                             marker=dict(symbol='star', size=18, color='yellow'), name='Pred Open'), row=1, col=1)

    # Volume + BOLD CYAN Line
    vol_colors = ['#26a69a' if df['Open'].iloc[i] < df['Close'].iloc[i] else '#ef5350' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='Volume'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='cyan', width=3.5), name='Vol Avg'), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. FINAL ANALYSIS DASHBOARD ---
    last_row = df.iloc[-1]
    st.subheader("Final Trading Analysis")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.write(f"**Live Price:** ₹{last_row['Close']:.2f}")
        st.write(f"**RSI Status:** {last_row['RSI']:.1f}")
    with c2:
        change_pct = ((prediction/last_row['Close'])-1)*100
        st.metric("Predicted Target", f"₹{prediction:.2f}", f"{change_pct:.2f}%")
    with c3:
        conf = "HIGH CONFIDENCE" if last_row['Volume'] > last_row['Vol_SMA'] else "FAKING"
        if last_row['Buy_S']: st.success(f"BUY | {conf}")
        elif last_row['Sell_S']: st.error(f"SELL | {conf}")
        else: st.info(f"NEUTRAL | {conf}")

    # Auto-refresh rerun
    time.sleep(refresh_rate)
    st.rerun()
