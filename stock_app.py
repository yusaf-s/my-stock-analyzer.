import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz

st.set_page_config(layout="wide", page_title="India Alpha: Silverline Ultimate")

# 1. Header & Time
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
st.title("🚀 India Alpha: Support & Resistance Edition")
st.write(f"🕒 **Market Time:** {current_time}")

# 2. Inputs
symbol = st.sidebar.text_input("Ticker", "500389.BO")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y"], index=2)

# 3. Data Engine
@st.cache_data
def get_data(ticker, pd_val):
    intvl = "5m" if pd_val == "1d" else "30m" if pd_val == "5d" else "1d"
    try:
        data = yf.download(ticker, period=pd_val, interval=intvl)
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except: return None

df = get_data(symbol, period)

if df is None or len(df) < 20:
    st.error("❌ Need more data. Try '1mo' or '1y' horizon.")
else:
    # --- INDICATORS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=15)
    
    # Calculate Pivot Points (Support/Resistance)
    # Pivot = (H+L+C)/3 | R1 = 2P - L | S1 = 2P - H
    last_h = df['High'].iloc[-2]
    last_l = df['Low'].iloc[-2]
    last_c = df['Close'].iloc[-2]
    pivot = (last_h + last_l + last_c) / 3
    resistance = (2 * pivot) - last_l
    support = (2 * pivot) - last_h

    # Bollinger Bands
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    df = pd.concat([df, bb], axis=1).copy()
    lower_band = df.filter(like='BBL').iloc[:,0]
    upper_band = df.filter(like='BBU').iloc[:,0]

    # Signal Logic
    df['Buy_Signal'] = (df['Close'] <= lower_band) & (df['RSI'] < 40)
    df['Sell_Signal'] = (df['Close'] >= upper_band) & (df['RSI'] > 60)

    # --- CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])

    # Price & Pivot Lines
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # Resistance Line (RED)
    fig.add_hline(y=resistance, line_dash="dot", line_color="red", 
                  annotation_text=f"RESISTANCE: {resistance:.2f}", row=1, col=1)
    # Support Line (GREEN)
    fig.add_hline(y=support, line_dash="dot", line_color="lime", 
                  annotation_text=f"SUPPORT: {support:.2f}", row=1, col=1)

    # Signals
    buy_pts = df[df['Buy_Signal']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.98, mode='markers+text', 
                             text="BUY", textfont=dict(color="lime"), 
                             marker=dict(symbol='triangle-up', color='lime'), name='BUY'), row=1, col=1)

    # Volume & RSI
    colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='white')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta')), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- FINAL VERDICT ---
    last_row = df.iloc[-1]
    curr_price = last_row['Close']
    
    st.subheader("Final Trading Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Price vs Support:** {((curr_price/support)-1)*100:.2f}% above floor")
        if curr_price >= resistance: st.warning("⚠️ CRITICAL: Testing Resistance!")
        elif curr_price <= support: st.success("💎 BARGAIN: At Support Floor")
    
    with col2:
        conf = "HIGH CONFIDENCE" if last_row['Volume'] > last_row['Vol_SMA'] else "WEAK/FAKING"
        if last_row['Buy_Signal']: st.success(f"BUY | {conf}")
        elif last_row['Sell_Signal']: st.error(f"SELL | {conf}")
        else: st.info(f"NEUTRAL (RSI: {last_row['RSI']:.2f})")
