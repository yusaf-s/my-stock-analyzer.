import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

st.set_page_config(layout="wide", page_title="Silverline 15m Circuit-Pro")

# --- NO-TYPE CONFIG ---
SYMBOL = "500389.BO"

st.title(f"🚀 Silverline Technologies (500389.BO) - 15m Pro")
st.info("💡 Note: If price is flat, the stock is locked in an Upper Circuit (₹20.58).")

def get_data():
    try:
        # We fetch 5 days of 15m data to ensure we ALWAYS have a working chart
        data = yf.download(SYMBOL, period="5d", interval="15m", progress=False)
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except: return None

df = get_data()

if df is not None and len(df) > 5:
    # 1. Indicators
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # 2. Safety Prediction Logic
    # Prevents "Length Mismatch" by using dynamic windowing
    window = min(15, len(df))
    y = df['Close'].tail(window).values
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    prediction = slope * (len(y) + 1) + intercept

    # 3. Signals (Large Labels)
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    if bb is not None:
        df = pd.concat([df, bb], axis=1)
        l_col, u_col = [c for c in df.columns if 'BBL' in c][0], [c for c in df.columns if 'BBU' in c][0]
        df['Buy_S'] = (df['Close'] <= df[l_col]) & (df['RSI'] < 45)
        df['Sell_S'] = (df['Close'] >= df[u_col]) & (df['RSI'] > 55)

    # 4. Chart Building
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    
    # Price & Prediction
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']), row=1, col=1)
    fig.add_trace(go.Scatter(x=[df.index[-1]], y=[prediction], mode='markers', marker=dict(symbol='star', size=18, color='yellow')), row=1, col=1)

    # Signal Markers
    for sig, color, pos in [('Buy_S', 'lime', 'bottom center'), ('Sell_S', 'red', 'top center')]:
        mask = df[df[sig]]
        if not mask.empty:
            lbls = ["STRONG " + sig[:3] if v > vs else sig[:3] for v, vs in zip(mask['Volume'], mask['Vol_SMA'])]
            fig.add_trace(go.Scatter(x=mask.index, y=mask['Low']*0.98 if 'Buy' in sig else mask['High']*1.02, 
                                     mode='markers+text', text=lbls, textposition=pos,
                                     textfont=dict(color=color, size=11, family="Arial Black"),
                                     marker=dict(symbol='triangle-up' if 'Buy' in sig else 'triangle-down', color=color, size=22)), row=1, col=1)

    # Volume + Thick Cyan Average
    colors = ['#26a69a' if o < c else '#ef5350' for o, c in zip(df['Open'], df['Close'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='cyan', width=4)), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # Status Dashboard
    c1, c2, c3 = st.columns(3)
    last = df.iloc[-1]
    c1.metric("Current Price", f"₹{last['Close']:.2f}")
    c2.metric("Target (Slope)", f"₹{prediction:.2f}", f"{((prediction/last['Close'])-1)*100:.2f}%")
    c3.write(f"**RSI:** {last['RSI']:.1f} | **Volume:** {'High' if last['Volume'] > last['Vol_SMA'] else 'Normal'}")

    time.sleep(30)
    st.rerun()
else:
    st.warning("🔄 Connecting to BSE... Please wait.")
    time.sleep(10)
    st.rerun()
