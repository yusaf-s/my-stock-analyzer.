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
st.set_page_config(layout="wide", page_title="Silverline Pro Tracker")

# UPDATED TICKER
SYMBOL = "SILVERLINE.BO"

# Time Logic
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title(f"🚀 Silverline Technologies Live (BSE)")
st.write(f"🕒 **Live IST:** {current_time} | *Refreshing every 30s*")

def get_live_data():
    try:
        # Fetching data - Period and Interval optimized for 15m analysis
        data = yf.download(SYMBOL, period="5d", interval="15m", progress=False)
        if data.empty: return None
        # Flatten MultiIndex columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

df = get_live_data()

if df is None or len(df) < 15:
    st.warning("🔄 Waiting for market data... Stock may be at Circuit Limit or Market is Closed.")
    time.sleep(10)
    st.rerun()
else:
    # --- CALCULATIONS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # Target Prediction (Linear Regression on last 10 bars)
    y_vals, x_vals = df['Close'].tail(10).values, np.arange(10)
    slope, intercept = np.polyfit(x_vals, y_vals, 1)
    prediction = slope * 11 + intercept

    # Bollinger Bands for Signal Logic
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    if bb is not None:
        df = pd.concat([df, bb], axis=1)
        l_col = [c for c in df.columns if 'BBL' in c][0]
        u_col = [c for c in df.columns if 'BBU' in c][0]
        df['Buy_S'] = (df['Close'] <= df[l_col]) & (df['RSI'] < 45)
        df['Sell_S'] = (df['Close'] >= df[u_col]) & (df['RSI'] > 55)

    # --- CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    # Price Candle
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    # Volume & Moving Average
    vol_colors = ['#26a69a' if o < c else '#ef5350' for o, c in zip(df['Open'], df['Close'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='cyan', width=2)), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2)), row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- FINAL ANALYSIS DASHBOARD ---
    last_row = df.iloc[-1]
    curr_price = last_row['Close']
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Signal")
        if last_row.get('Buy_S'): st.success("🟢 STRONG BUY")
        elif last_row.get('Sell_S'): st.error("🔴 STRONG SELL")
        else: st.info("⚪ NEUTRAL")
        st.write(f"RSI (14): {last_row['RSI']:.1f}")

    with col2:
        st.subheader("Targeting")
        # Current Price placed immediately before Predicted Target
        st.write(f"Current Price: **₹{curr_price:.2f}**")
        change_pct = ((prediction / curr_price) - 1) * 100
        st.metric("Predicted Target", f"₹{prediction:.2f}", f"{change_pct:.2f}%")

    with col3:
        st.subheader("Volume")
        vol_ratio = (last_row['Volume'] / last_row['Vol_SMA']) * 100
        st.write(f"Vol Strength: {vol_ratio:.1f}%")
        st.write("Avg Vol (20): " + f"{last_row['Vol_SMA']:.0f}")

    # Auto-refresh logic
    time.sleep(30)
    st.rerun()
