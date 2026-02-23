import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- CONFIG ---
SYMBOL = "SILVERLINE.BO"
st.set_page_config(layout="wide", page_title="Silverline Timeline Master")

st.title(f"📊 Silverline Technologies: Multi-Timeline Analysis")

# 1. Timeline Selector
st.sidebar.header("Select Timeline")
view_mode = st.sidebar.selectbox(
    "Choose View:", 
    ["1 Day (Live 1m)", "5 Day (15m)", "1 Month (Hourly)"],
    index=1
)

# 2. Logic to map selections to YFinance
mapping = {
    "1 Day (Live 1m)": {"p": "1d", "i": "1m"},
    "5 Day (15m)": {"p": "5d", "i": "15m"},
    "1 Month (Hourly)": {"p": "1mo", "i": "1h"}
}

def get_data():
    conf = mapping[view_mode]
    try:
        data = yf.download(SYMBOL, period=conf["p"], interval=conf["i"], progress=False)
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except: return None

df = get_data()

if df is not None and len(df) > 5:
    # --- INDICATORS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # Trend Math
    y = df['Close'].tail(15).values
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    prediction = slope * (len(y) + 1) + intercept

    # --- CHART ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='cyan'), row=2, col=1)
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- DASHBOARD (Current Price last before Target) ---
    c1, c2, c3 = st.columns(3)
    curr_price = df['Close'].iloc[-1]
    
    c1.metric("Timeline Status", view_mode)
    c2.write(f"Current Price: **₹{curr_price:.2f}**")
    c2.metric("Predicted Target", f"₹{prediction:.2f}", f"{((prediction/curr_price)-1)*100:.2f}%")
    c3.metric("RSI (14)", f"{df['RSI'].iloc[-1]:.1f}")

    time.sleep(30)
    st.rerun()
else:
    st.error(f"⚠️ No {view_mode} data found. Stock is likely locked in a Circuit.")
    st.info("Try switching to '5 Day' or '1 Month' in the sidebar for historical context.")
