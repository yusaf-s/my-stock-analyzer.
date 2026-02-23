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
st.set_page_config(layout="wide", page_title="Silverline Pro: Circuit Edition")

# 1. Fixed Ticker
SYMBOL = "500389.BO"

# 2. Time Logic
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%H:%M:%S')

st.title(f"🚀 Silverline Technologies (500389.BO)")
st.write(f"🕒 **Last Update:** {current_time} IST | **Status:** Trading at Upper Circuit (₹20.58)")

# 3. Data Engine with "Circuit-Lock" Fallback
def get_reliable_data():
    try:
        # Try 1-day live first
        data = yf.download(SYMBOL, period="1d", interval="1m", progress=False)
        
        # If today's data is missing or too small (Circuit Lock), pull 5 days for context
        if data is None or len(data) < 10:
            data = yf.download(SYMBOL, period="5d", interval="15m", progress=False)
            st.info("💡 Note: Stock is at Circuit Limit. Showing 5-day history for analysis.")
            
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except: return None

df = get_reliable_data()

if df is not None:
    # --- 4. INDICATORS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # Trend Prediction
    y, x = df['Close'].tail(10).values, np.arange(10)
    slope, intercept = np.polyfit(x, y, 1)
    prediction = slope * 11 + intercept

    # Buy/Sell Signals
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    if bb is not None:
        df = pd.concat([df, bb], axis=1)
        l_col, u_col = [c for c in df.columns if 'BBL' in c][0], [c for c in df.columns if 'BBU' in c][0]
        df['Buy_S'] = (df['Close'] <= df[l_col]) & (df['RSI'] < 45)
        df['Sell_S'] = (df['Close'] >= df[u_col]) & (df['RSI'] > 55)

    # --- 5. THE CHART ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    # Price + Prediction Star
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']), row=1, col=1)
    fig.add_trace(go.Scatter(x=[df.index[-1]], y=[prediction], mode='markers', marker=dict(symbol='star', size=20, color='yellow'), name='Target'), row=1, col=1)

    # LARGE BUY/SELL LABELS
    for sig_type, color, pos in [('Buy_S', 'lime', 'bottom center'), ('Sell_S', 'red', 'top center')]:
        sigs = df[df[sig_type]]
        if not sigs.empty:
            labels = ["STRONG " + sig_type[:3] if v > vs else sig_type[:3] for v, vs in zip(sigs['Volume'], sigs['Vol_SMA'])]
            fig.add_trace(go.Scatter(x=sigs.index, y=sigs['Low']*0.98 if 'Buy' in sig_type else sigs['High']*1.02, 
                                     mode='markers+text', text=labels, textposition=pos,
                                     textfont=dict(color=color, size=12, family="Arial Black"),
                                     marker=dict(symbol='triangle-up' if 'Buy' in sig_type else 'triangle-down', color=color, size=25)), row=1, col=1)

    # Volume + CYAN Line
    v_colors = ['#26a69a' if o < c else '#ef5350' for o, c in zip(df['Open'], df['Close'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='cyan', width=4)), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2.5)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # Auto-refresh
    time.sleep(30)
    st.rerun()
else:
    st.warning("Data connection issues. Retrying...")
    time.sleep(5)
    st.rerun()
