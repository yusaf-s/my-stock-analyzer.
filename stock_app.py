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
st.set_page_config(layout="wide", page_title="India Alpha: Support & Resistance Pro")

# 1. Header & Time Logic
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Support & Resistance Edition")
st.write(f"🕒 **Current Market Time (IST):** {current_time}")

# 2. Sidebar Inputs
symbol = st.sidebar.text_input("Ticker", "500389.BO")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y", "5y"], index=0)

# 3. Smart Data Engine (Handles Mondays/Weekends)
@st.cache_data
def get_data(ticker, pd_val):
    interval_map = {"1d": "1m", "5d": "5m", "1mo": "1d", "1y": "1d", "5y": "1d"}
    try:
        # Initial pull for the requested period
        data = yf.download(ticker, period=pd_val, interval=interval_map[pd_val])
        
        # SMART FALLBACK: If 1d is selected but today has no data (Monday morning/Weekend)
        if pd_val == "1d" and (data is None or len(data) < 5):
            # Pull last 4 days to find the most recent active trading session (Friday)
            fallback_data = yf.download(ticker, period="4d", interval="1m")
            if not fallback_data.empty:
                last_date = fallback_data.index[-1].date()
                data = fallback_data[fallback_data.index.date == last_date]
                st.info(f"📊 Market hasn't opened today. Showing last session: {last_date}")
        
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

df = get_data(symbol, period)

if df is None or len(df) < 5:
    st.error("❌ No market data found. Check the ticker symbol or try '5d'.")
else:
    # --- 4. INDICATORS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=15)
    
    # Dynamic Support/Resistance (Pivot Points)
    last_h, last_l, last_c = df['High'].max(), df['Low'].min(), df['Close'].iloc[-1]
    pivot = (last_h + last_l + last_c) / 3
    resistance = (2 * pivot) - last_l
    support = (2 * pivot) - last_h

    # Bollinger Bands for Signal Generation
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    df = pd.concat([df, bb], axis=1).copy()
    l_band = df.filter(like='BBL').iloc[:,0]
    u_band = df.filter(like='BBU').iloc[:,0]

    # Signal Logic
    df['Buy_Signal'] = (df['Close'] <= l_band) & (df['RSI'] < 45)
    df['Sell_Signal'] = (df['Close'] >= u_band) & (df['RSI'] > 55)

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])

    # Candlestick Price Chart
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # S/R Lines
    fig.add_hline(y=resistance, line_dash="dot", line_color="red", annotation_text="RESISTANCE", row=1, col=1)
    fig.add_hline(y=support, line_dash="dot", line_color="lime", annotation_text="SUPPORT", row=1, col=1)

    # Signal Markers
    buy_pts = df[df['Buy_Signal']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.998, mode='markers+text', 
                             text="BUY", textfont=dict(color="lime"), 
                             marker=dict(symbol='triangle-up', color='lime'), name='BUY'), row=1, col=1)

    # Volume & Average Line
    vol_colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='Volume'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='white', width=1), name='Avg Vol'), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name='RSI'), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. FINAL ANALYSIS DASHBOARD ---
    last_row = df.iloc[-1]
    curr_price = last_row['Close']
    
    st.subheader("Final Trading Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Price Position:** {((curr_price/support)-1)*100:.2f}% above Support")
        if curr_price >= resistance: 
            st.warning("⚠️ ALERT: Price hitting Resistance ceiling.")
        elif curr_price <= support: 
            st.success("💎 OPPORTUNITY: Price at Support floor.")
        else:
            st.write("Market currently trading between levels.")
    
    with col2:
        # Confidence logic based on Volume vs Avg (White Line)
        vol_avg = last_row['Vol_SMA']
        curr_vol = last_row['Volume']
        
        if curr_vol >= vol_avg:
            confidence_level = "HIGH CONFIDENCE"
        elif curr_vol >= (vol_avg / 2):
            confidence_level = "AVERAGE STRENGTH"
        else:
            confidence_level = "FAKING"

        # Signal Output with requested Confidence words
        if last_row['Buy_Signal']:
            st.success(f"BUY | {confidence_level}")
        elif last_row['Sell_Signal']:
            st.error(f"SELL | {confidence_level}")
        else:
            st.info(f"NEUTRAL (RSI: {last_row['RSI']:.1f}) | {confidence_level}")

    st.divider()
    st.download_button("📥 Download Data", df.to_csv().encode('utf-8'), f"{symbol}.csv", "text/csv")
