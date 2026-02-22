import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz

st.set_page_config(layout="wide", page_title="India Alpha Analyzer")

# Header with Current Time
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Advanced Stock Analyzer")
st.write(f"🕒 **Current Market Time (IST):** {current_time}")

# 1. Inputs (Updated for 1d and 1wk)
symbol = st.sidebar.text_input("Ticker (NSE: .NS | BSE: .BO)", "SBIN.NS")
period = st.sidebar.selectbox("Analysis Horizon", ["1d", "5d", "1mo", "1y", "5y"], index=3)
# Note: yfinance uses '5d' for a business week and '1mo' for a month

# 2. Data Engine (Enhanced for Intraday/Short term)
@st.cache_data
def get_data(ticker, pd_val):
    # Determine interval based on horizon
    if pd_val == "1d": intvl = "5m"
    elif pd_val == "5d": intvl = "30m"
    else: intvl = "1d"
    
    try:
        data = yf.download(ticker, period=pd_val, interval=intvl)
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except: return None

df = get_data(symbol, period)

if df is None or len(df) < 5:
    st.error(f"❌ No data found for {symbol}. Try SBIN.NS for NSE or 500389.BO for Silverline (BSE).")
else:
    # 3. Technicals
    df['RSI'] = ta.rsi(df['Close'], length=14)
    bb = ta.bbands(df['Close'], length=20, std=2)
    df = pd.concat([df, bb], axis=1).copy()
    
    # 4. Charting
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3],
                        subplot_titles=('Price & BBands', 'Volume', 'RSI'))

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # Bollinger Bands
    if not df.filter(like='BBU').empty:
        fig.add_trace(go.Scatter(x=df.index, y=df.filter(like='BBU').iloc[:,0], 
                                 line=dict(color='rgba(173, 216, 230, 0.4)'), name='Upper Band'), row=1, col=1)
    if not df.filter(like='BBL').empty:
        fig.add_trace(go.Scatter(x=df.index, y=df.filter(like='BBL').iloc[:,0], 
                                 fill='tonexty', line=dict(color='rgba(173, 216, 230, 0.4)'), name='Lower Band'), row=1, col=1)

    # Volume & RSI
    colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name='RSI'), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # 5. Dashboard Verdict
    st.subheader("Current Market Verdict")
    last_row = df.iloc[-1]
    rsi_val = last_row['RSI']
    
    if rsi_val < 35: signal, color = "BUY (Oversold)", "green"
    elif rsi_val > 65: signal, color = "SELL (Overbought)", "red"
    else: signal, color = "NEUTRAL", "white"
    
    st.markdown(f"### Signal: :{color}[{signal}] (RSI: {rsi_val:.2f})")
