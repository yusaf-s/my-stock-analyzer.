import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- FIXED TICKER ---
SYMBOL = "500389.BO"

st.set_page_config(layout="wide", page_title="Silverline Pro Fix")
st.title(f"🚀 Silverline Technologies (15m + 1d Fix)")

# 1. Data Fetcher with Error Handling
def get_clean_data():
    try:
        # Try to get 15-minute data for the last 5 days (more reliable than 1d)
        data = yf.download(SYMBOL, period="5d", interval="15m", progress=False)
        
        if data.empty or len(data) < 20:
            st.warning("Waiting for market data... Stock might be locked in Circuit.")
            return None
            
        # Fix for new yfinance multi-index format
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        return data
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

df = get_clean_data()

if df is not None:
    # 2. INDICATORS
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # --- TREND PREDICTION (The part that crashed) ---
    # We only run this if we have at least 15 rows of data
    if len(df) >= 15:
        # Use tail(15) to ensure we always have a fixed number of points
        recent_data = df['Close'].tail(15).values
        x_axis = np.arange(len(recent_data))
        slope, intercept = np.polyfit(x_axis, recent_data, 1)
        prediction = slope * (len(recent_data) + 1) + intercept
    else:
        prediction = df['Close'].iloc[-1] # Fallback if data is too short

    # 3. CHARTING
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # Candlestick
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    # Cyan Volume Line (Highly Visible)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='cyan', width=3), name='Vol Avg'), row=2, col=1)

    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # 4. ANALYSIS BOX
    st.success(f"LIVE PRICE: ₹{df['Close'].iloc[-1]:.2f} | RSI: {df['RSI'].iloc[-1]:.2f}")
    
    time.sleep(30)
    st.rerun()
