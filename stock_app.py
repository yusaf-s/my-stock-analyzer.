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
st.set_page_config(layout="wide", page_title="India Alpha: Pro Analyzer")

# 1. Header & Time Logic
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Silverline Pro")
st.write(f"🕒 **Current Market Time (IST):** {current_time}")

# 2. Sidebar Inputs
symbol = st.sidebar.text_input("Ticker", "500389.BO")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y", "5y"], index=0)

# 3. Smart Data Engine
@st.cache_data
def get_data(ticker, pd_val):
    interval_map = {"1d": "1m", "5d": "5m", "1mo": "1d", "1y": "1d", "5y": "1d"}
    try:
        data = yf.download(ticker, period=pd_val, interval=interval_map[pd_val])
        
        # Fallback for Monday/Weekend
        if pd_val == "1d" and (data is None or len(data) < 10):
            data = yf.download(ticker, period="4d", interval="1m")
            if not data.empty:
                last_date = data.index[-1].date()
                data = data[data.index.date == last_date]
                st.info(f"📊 Market Closed. Showing session: {last_date}")
        
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

df = get_data(symbol, period)

if df is None or len(df) < 20:
    st.error("❌ Not enough data yet. Please wait for market open or try '5d'.")
else:
    # --- 4. INDICATORS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20) # This is the "White Line"
    
    # Bollinger Bands - Updated to handle errors
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    
    # Check if BB was successful
    if bb is not None and not bb.empty:
        df = pd.concat([df, bb], axis=1)
        l_col = [c for c in df.columns if 'BBL' in c][0]
        u_col = [c for c in df.columns if 'BBU' in c][0]
        df['Buy_Signal'] = (df['Close'] <= df[l_col]) & (df['RSI'] < 45)
        df['Sell_Signal'] = (df['Close'] >= df[u_col]) & (df['RSI'] > 55)
    else:
        df['Buy_Signal'] = False
        df['Sell_Signal'] = False

    # S/R Pivot Logic
    last_h, last_l, last_c = df['High'].max(), df['Low'].min(), df['Close'].iloc[-1]
    pivot = (last_h + last_l + last_c) / 3
    resistance = (2 * pivot) - last_l
    support = (2 * pivot) - last_h

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    fig.add_hline(y=resistance, line_dash="dot", line_color="red", annotation_text="RES", row=1, col=1)
    fig.add_hline(y=support, line_dash="dot", line_color="lime", annotation_text="SUP", row=1, col=1)

    # Signal Labels
    buy_pts = df[df['Buy_Signal']]
    if not buy_pts.empty:
        fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.99, mode='markers+text', 
                                 text="BUY", textfont=dict(color="lime"), marker=dict(symbol='triangle-up', color='lime')), row=1, col=1)

    # Volume + White Average Line
    vol_colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='Volume'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='white', width=1.5), name='Avg Vol'), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta')), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. FINAL ANALYSIS ---
    last_row = df.iloc[-1]
    curr_vol = last_row['Volume']
    vol_avg = last_row['Vol_SMA']
    
    # Volume Confidence Logic
    if curr_vol >= vol_avg:
        confidence = "HIGH CONFIDENCE"
    elif curr_vol >= (vol_avg / 2):
        confidence = "AVERAGE STRENGTH"
    else:
        confidence = "FAKING"

    st.subheader("Final Trading Analysis")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Current RSI:** {last_row['RSI']:.2f}")
        st.write(f"**Volume vs Avg:** {curr_vol:.0f} / {vol_avg:.0f}")
    
    with col2:
        if last_row['Buy_Signal']:
            st.success(f"BUY | {confidence}")
        elif last_row['Sell_Signal']:
            st.error(f"SELL | {confidence}")
        else:
            st.info(f"NEUTRAL | {confidence}")

    st.divider()
    st.download_button("📥 Download Analysis", df.to_csv().encode('utf-8'), f"{symbol}.csv", "text/csv")
              
