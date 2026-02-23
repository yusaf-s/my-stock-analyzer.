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
st.set_page_config(layout="wide", page_title="India Alpha: Silverline Pro")

# 1. Header & Automatic Time
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Silverline Technologies (500389.BO)")
st.write(f"🕒 **Live Market Time (IST):** {current_time}")

# 2. Sidebar - HARDCODED DEFAULTS
# No more typing! It opens Silverline by default.
symbol = st.sidebar.text_input("Ticker", value="500389.BO") 

# Added 15m specifically for best analysis results
pd_val = st.sidebar.selectbox("Select Timeframe", 
                              options=["15m (Best)", "1d (Live)", "5d", "1mo", "1y"], 
                              index=0)

# 3. Data Engine (Mapping Intervals)
def get_live_data(ticker, timeframe):
    # Mapping the selection to Yahoo Finance intervals
    mapping = {
        "15m (Best)": {"p": "5d", "i": "15m"},
        "1d (Live)": {"p": "1d", "i": "1m"},
        "5d": {"p": "5d", "i": "5m"},
        "1mo": {"p": "1mo", "i": "1h"},
        "1y": {"p": "1y", "i": "1d"}
    }
    conf = mapping[timeframe]
    try:
        data = yf.download(ticker, period=conf["p"], interval=conf["i"], progress=False)
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except: return None

df = get_live_data(symbol, pd_val)

if df is None or len(df) < 15:
    st.warning("⚠️ Market is currently closed or Data is refreshing. Please wait 30s...")
    time.sleep(30)
    st.rerun()
else:
    # --- 4. INDICATORS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # Prediction logic
    y_vals, x_vals = df['Close'].tail(10).values, np.arange(10)
    slope, intercept = np.polyfit(x_vals, y_vals, 1)
    prediction = slope * 11 + intercept

    # Signals
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

    # Candlesticks
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    # LARGE LABELS: STRONG BUY / BUY
    buys = df[df['Buy_S']].copy()
    if not buys.empty:
        buys['lbl'] = buys.apply(lambda x: "STRONG BUY" if x['Volume'] > x['Vol_SMA'] else "BUY", axis=1)
        fig.add_trace(go.Scatter(x=buys.index, y=buys['Low']*0.985, mode='markers+text',
                                 text=buys['lbl'], textposition="bottom center",
                                 textfont=dict(color="lime", size=11, family="Arial Black"),
                                 marker=dict(symbol='triangle-up', color='lime', size=25)), row=1, col=1)

    # LARGE LABELS: STRONG SELL / SELL
    sells = df[df['Sell_S']].copy()
    if not sells.empty:
        sells['lbl'] = sells.apply(lambda x: "STRONG SELL" if x['Volume'] > x['Vol_SMA'] else "SELL", axis=1)
        fig.add_trace(go.Scatter(x=sells.index, y=sells['High']*1.015, mode='markers+text',
                                 text=sells['lbl'], textposition="top center",
                                 textfont=dict(color="red", size=11, family="Arial Black"),
                                 marker=dict(symbol='triangle-down', color='red', size=25)), row=1, col=1)

    # Yellow Star Prediction
    fig.add_trace(go.Scatter(x=[df.index[-1]], y=[prediction], mode='markers',
                             marker=dict(symbol='star', size=20, color='yellow'), name='Next Target'), row=1, col=1)

    # Volume + Thick Cyan Line
    v_colors = ['#26a69a' if df['Open'].iloc[i] < df['Close'].iloc[i] else '#ef5350' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='cyan', width=4)), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2.5)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. FINAL ANALYSIS DASHBOARD ---
    last_row = df.iloc[-1]
    st.subheader("Final Trading Analysis")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.write(f"**Current Price:** ₹{last_row['Close']:.2f}")
        st.write(f"**Volume Status:** {'Bullish Surge' if last_row['Volume'] > last_row['Vol_SMA'] else 'Stable'}")
    with c2:
        change = ((prediction/last_row['Close'])-1)*100
        st.metric("Predicted Target", f"₹{prediction:.2f}", f"{change:.2f}%")
    with c3:
        conf = "HIGH CONFIDENCE" if last_row['Volume'] > last_row['Vol_SMA'] else "LOW VOLUME"
        if last_row['Buy_S']: st.success(f"BUY | {conf}")
        elif last_row['Sell_S']: st.error(f"SELL | {conf}")
        else: st.info(f"NEUTRAL")

    # Real-Time Heartbeat
    time.sleep(30)
    st.rerun()
