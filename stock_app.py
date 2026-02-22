import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz

st.set_page_config(layout="wide", page_title="India Alpha Pro")

# Header with Current Time
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Pro Analyzer")
st.write(f"🕒 **Market Time:** {current_time}")

# 1. Inputs
symbol = st.sidebar.text_input("Ticker (e.g., SBIN.NS)", "SBIN.NS")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y", "5y"], index=3)

# 2. Data Engine
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
    st.error("❌ Not enough data. Try a longer timeframe.")
else:
    # 3. Calculations
    df['RSI'] = ta.rsi(df['Close'], length=14)
    bb = ta.bbands(df['Close'], length=20, std=2)
    # NEW: Volume Moving Average
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    df = pd.concat([df, bb], axis=1).copy()
    
    # Signal Logic
    lower_band = df.filter(like='BBL').iloc[:,0]
    upper_band = df.filter(like='BBU').iloc[:,0]
    df['Buy_Signal'] = (df['Close'] < lower_band) & (df['RSI'] < 35)
    df['Sell_Signal'] = (df['Close'] > upper_band) & (df['RSI'] > 65)

    # 4. Professional Charting
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3],
                        subplot_titles=('Price & Trade Signals', 'Volume (with Avg)', 'RSI'))

    # Price Trace
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # BUY/SELL Text Labels
    buy_pts = df[df['Buy_Signal']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.97, mode='markers+text', 
                             text="BUY", textposition="bottom center",
                             marker=dict(symbol='triangle-up', color='lime', size=10), name='BUY'), row=1, col=1)

    sell_pts = df[df['Sell_Signal']]
    fig.add_trace(go.Scatter(x=sell_pts.index, y=sell_pts['High']*1.03, mode='markers+text', 
                             text="SELL", textposition="top center",
                             marker=dict(symbol='triangle-down', color='red', size=10), name='SELL'), row=1, col=1)

    # Volume Trace + NEW Volume SMA
    colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='white', width=1.5), name='Vol Avg'), row=2, col=1)

    # RSI Trace
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name='RSI'), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # 5. Verdict & Download
    last_row = df.iloc[-1]
    vol_status = "High Volume" if last_row['Volume'] > last_row['Vol_SMA'] else "Normal Volume"
    
    st.subheader(f"Current Verdict ({vol_status})")
    if last_row['Buy_Signal']: st.success(f"🚀 BUY NOW (Vol: {vol_status})")
    elif last_row['Sell_Signal']: st.error(f"⚠️ SELL NOW (Vol: {vol_status})")
    else: st.info(f"⚖️ NEUTRAL (RSI: {last_row['RSI']:.2f})")

    st.divider()
    csv = df.to_csv().encode('utf-8')
    st.download_button("📥 Download Analysis (CSV)", data=csv, file_name=f"{symbol}.csv", mime="text/csv")
