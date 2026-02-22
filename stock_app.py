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
st.set_page_config(layout="wide", page_title="India Alpha: Silverline Predictor")

# 1. Header & Time Logic
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Silverline Technologies")
st.write(f"🕒 **Current Market Time (IST):** {current_time}")

# 2. Sidebar Inputs
symbol = st.sidebar.text_input("Ticker", "500389.BO")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y"], index=0)

# 3. Smart Data Engine
@st.cache_data
def get_data(ticker, pd_val):
    interval_map = {"1d": "1m", "5d": "5m", "1mo": "1d", "1y": "1d"}
    try:
        data = yf.download(ticker, period=pd_val, interval=interval_map[pd_val])
        
        # Monday/Weekend Fallback logic
        if pd_val == "1d" and (data is None or len(data) < 10):
            data = yf.download(ticker, period="4d", interval="1m")
            if not data.empty:
                last_date = data.index[-1].date()
                data = data[data.index.date == last_date]
                st.info(f"📊 Showing last active session: {last_date}")
        
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

df = get_data(symbol, period)

if df is None or len(df) < 15:
    st.error("❌ Data unavailable for Silverline at this time.")
else:
    # --- 4. INDICATORS & PREDICTION ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # Linear Regression Prediction (Last 10 bars)
    y_vals = df['Close'].tail(10).values
    x_vals = np.arange(len(y_vals))
    slope, intercept = np.polyfit(x_vals, y_vals, 1)
    prediction = slope * (len(y_vals) + 1) + intercept
    
    # Support/Resistance Pivot logic
    last_h, last_l, last_c = df['High'].max(), df['Low'].min(), df['Close'].iloc[-1]
    pivot = (last_h + last_l + last_c) / 3
    res_level = (2 * pivot) - last_l
    sup_level = (2 * pivot) - last_h

    # Bollinger Bands
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    if bb is not None and not bb.empty:
        df = pd.concat([df, bb], axis=1)
        l_col = [c for c in df.columns if 'BBL' in c][0]
        u_col = [c for c in df.columns if 'BBU' in c][0]
        df['Buy_S'] = (df['Close'] <= df[l_col]) & (df['RSI'] < 45)
        df['Sell_S'] = (df['Close'] >= df[u_col]) & (df['RSI'] > 55)
    else:
        df['Buy_S'] = df['Sell_S'] = False

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # Prediction Star
    fig.add_trace(go.Scatter(x=[df.index[-1]], y=[prediction], mode='markers', 
                             marker=dict(symbol='star', size=15, color='yellow'), name='Pred Price'), row=1, col=1)

    fig.add_hline(y=res_level, line_dash="dot", line_color="red", annotation_text="RES", row=1, col=1)
    fig.add_hline(y=sup_level, line_dash="dot", line_color="lime", annotation_text="SUP", row=1, col=1)

    vol_colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='white', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta')), row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. FINAL TRADING ANALYSIS (WITH PREDICTION) ---
    last_row = df.iloc[-1]
    curr_price = last_row['Close']
    
    st.subheader("Final Trading Analysis")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**Market Sentiment**")
        dist_to_sup = ((curr_price/sup_level)-1)*100
        st.write(f"📍 Price: ₹{curr_price:.2f}")
        st.write(f"🛡️ Safety: {dist_to_sup:.2f}% above Support")
        if curr_price >= res_level: st.warning("⚠️ At Resistance")

    with col2:
        st.write("**Prediction Target**")
        change_pct = ((prediction/curr_price)-1)*100
        st.metric("Predicted Open", f"₹{prediction:.2f}", f"{change_pct:.2f}%")
        st.write("*(Based on 10-bar momentum)*")

    with col3:
        st.write("**Signal & Confidence**")
        # Confidence logic
        vol_avg = last_row['Vol_SMA']
        curr_vol = last_row['Volume']
        if curr_vol >= vol_avg: confidence = "HIGH CONFIDENCE"
        elif curr_vol >= (vol_avg / 2): confidence = "AVERAGE STRENGTH"
        else: confidence = "FAKING"
        
        # Display Signal
        if last_row['Buy_S']: st.success(f"BUY | {confidence}")
        elif last_row['Sell_S']: st.error(f"SELL | {confidence}")
        else: st.info(f"NEUTRAL | {confidence}")

    st.divider()
    st.download_button("📥 Export CSV", df.to_csv().encode('utf-8'), f"{symbol}.csv", "text/csv")
      
