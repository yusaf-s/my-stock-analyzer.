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
st.set_page_config(layout="wide", page_title="India Alpha: Universal Analyzer")

# 1. Header & Time
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Multi-Timeframe Pro")
st.write(f"🕒 **Market Time (IST):** {current_time}")

# 2. Sidebar Inputs (Now with 1d and 5d restored)
symbol = st.sidebar.text_input("Ticker", "500389.BO")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y", "5y"], index=2)

# 3. Smart Data Engine (Auto-switches interval based on period)
@st.cache_data
def get_data(ticker, pd_val):
    # If period is 1 day, get 1-minute bars. If 5 days, get 15-minute bars.
    interval_map = {"1d": "1m", "5d": "15m", "1mo": "1d", "1y": "1d", "5y": "1d"}
    try:
        data = yf.download(ticker, period=pd_val, interval=interval_map[pd_val])
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

df = get_data(symbol, period)

if df is None or len(df) < 10:
    st.error("❌ Data not available for this period. Try '5d' or '1mo'.")
else:
    # --- 4. INDICATORS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=15)
    
    # Trend Prediction (Uses last 15 data points)
    # On '1d' view, this predicts the next few minutes. On '1mo' it predicts tomorrow.
    lookback = min(len(df), 15)
    y_vals = df['Close'].tail(lookback).values
    x_vals = np.arange(len(y_vals))
    slope, intercept = np.polyfit(x_vals, y_vals, 1)
    prediction = slope * (len(y_vals) + 1) + intercept
    trend_dir = "UP 📈" if slope > 0 else "DOWN 📉"

    # Support/Resistance (Pivot Points)
    last_h, last_l, last_c = df['High'].iloc[-1], df['Low'].iloc[-1], df['Close'].iloc[-1]
    pivot = (last_h + last_l + last_c) / 3
    res_level = (2 * pivot) - last_l
    sup_level = (2 * pivot) - last_h

    # Bollinger Bands
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    df = pd.concat([df, bb], axis=1).copy()
    l_band = df.filter(like='BBL').iloc[:,0]
    u_band = df.filter(like='BBU').iloc[:,0]
    
    # Signals
    df['Buy_S'] = (df['Close'] <= l_band) & (df['RSI'] < 40)
    df['Sell_S'] = (df['Close'] >= u_band) & (df['RSI'] > 60)

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])

    # Candlestick
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # Prediction Star
    fig.add_trace(go.Scatter(x=[df.index[-1]], y=[prediction], mode='markers', 
                             marker=dict(symbol='star', size=15, color='yellow'), name='Target'), row=1, col=1)

    # Levels
    fig.add_hline(y=res_level, line_dash="dot", line_color="red", annotation_text="RES", row=1, col=1)
    fig.add_hline(y=sup_level, line_dash="dot", line_color="lime", annotation_text="SUP", row=1, col=1)

    # Signals
    buy_pts = df[df['Buy_S']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.99, mode='markers+text', 
                             text="BUY", textfont=dict(color="lime"), 
                             marker=dict(symbol='triangle-up', color='lime'), name='BUY'), row=1, col=1)

    # Volume & RSI
    vol_colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta')), row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. DASHBOARD ---
    st.subheader(f"Analysis for {period} Horizon")
    c1, c2, c3 = st.columns(3)
    c1.metric("Trend", trend_dir)
    c2.metric("Target", f"₹{prediction:.2f}")
    c3.metric("RSI", f"{df['RSI'].iloc[-1]:.1f}")
    
    if last_row := df.iloc[-1]:
        conf = "HIGH" if last_row['Volume'] > last_row['Vol_SMA'] else "LOW"
        if last_row['Buy_S']: st.success(f"🚀 BUY SIGNAL | Confidence: {conf}")
        elif last_row['Sell_S']: st.error(f"⚠️ SELL SIGNAL | Confidence: {conf}")
    
