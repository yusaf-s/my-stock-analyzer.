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
st.set_page_config(layout="wide", page_title="India Alpha: Ultimate Predictor")

# 1. Header & Time Logic
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

st.title("🚀 India Alpha: Ultimate Trend Predictor")
st.write(f"🕒 **Market Time (IST):** {current_time}")

# 2. Sidebar Inputs
symbol = st.sidebar.text_input("Ticker (e.g., 500389.BO or SBIN.NS)", "500389.BO")
period = st.sidebar.selectbox("Horizon", ["1mo", "1y", "5y"], index=0)

# 3. Data Engine
@st.cache_data
def get_data(ticker, pd_val):
    try:
        # We use 1d interval for cleaner prediction math
        data = yf.download(ticker, period=pd_val, interval="1d")
        if data.empty: return None
        # Clean up multi-index columns if they exist
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception as e:
        return None

df = get_data(symbol, period)

if df is None or len(df) < 20:
    st.error("❌ Not enough data. Please select a longer horizon like '1mo' or '1y'.")
else:
    # --- 4. INDICATORS & PREDICTION MATH ---
    # RSI & Volume SMA
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=15)
    
    # Trend Prediction (Linear Regression on last 10 days)
    y_vals = df['Close'].tail(10).values
    x_vals = np.arange(len(y_vals))
    slope, intercept = np.polyfit(x_vals, y_vals, 1)
    prediction = slope * (len(y_vals) + 1) + intercept
    trend_direction = "UP 📈" if slope > 0 else "DOWN 📉"

    # Pivot Points (Support/Resistance)
    last_h = df['High'].iloc[-2]
    last_l = df['Low'].iloc[-2]
    last_c = df['Close'].iloc[-2]
    pivot = (last_h + last_l + last_c) / 3
    res_level = (2 * pivot) - last_l
    sup_level = (2 * pivot) - last_h

    # Bollinger Bands for Signals
    bb = ta.bbands(df['Close'], length=20, std=1.5)
    df = pd.concat([df, bb], axis=1).copy()
    l_band = df.filter(like='BBL').iloc[:,0]
    u_band = df.filter(like='BBU').iloc[:,0]
    
    # Signal Logic
    df['Buy_S'] = (df['Close'] <= l_band) & (df['RSI'] < 45)
    df['Sell_S'] = (df['Close'] >= u_band) & (df['RSI'] > 55)

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3],
                        subplot_titles=('Price, Levels & Prediction', 'Volume vs Avg', 'RSI Momentum'))

    # Candlestick Trace
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # Support & Resistance Lines
    fig.add_hline(y=res_level, line_dash="dot", line_color="red", 
                  annotation_text=f"RES: {res_level:.2f}", row=1, col=1)
    fig.add_hline(y=sup_level, line_dash="dot", line_color="lime", 
                  annotation_text=f"SUP: {sup_level:.2f}", row=1, col=1)

    # Prediction Target (Yellow Star)
    fig.add_trace(go.Scatter(x=[df.index[-1]], y=[prediction], mode='markers', 
                             marker=dict(symbol='star', size=15, color='yellow'), 
                             name='Predicted Target'), row=1, col=1)

    # Trade Signals (Text labels)
    buy_pts = df[df['Buy_S']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.98, mode='markers+text', 
                             text="BUY", textfont=dict(color="lime"), 
                             marker=dict(symbol='triangle-up', color='lime', size=10), name='BUY'), row=1, col=1)

    sell_pts = df[df['Sell_S']]
    fig.add_trace(go.Scatter(x=sell_pts.index, y=sell_pts['High']*1.02, mode='markers+text', 
                             text="SELL", textfont=dict(color="red"), 
                             marker=dict(symbol='triangle-down', color='red', size=10), name='SELL'), row=1, col=1)

    # Volume & RSI
    vol_colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='Volume'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Vol_SMA'], line=dict(color='white', width=1), name='Vol Avg'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name='RSI'), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    # Chart Layout
    fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. PREDICTION DASHBOARD ---
    st.subheader("🔮 Predictive Insights")
    last_row = df.iloc[-1]
    curr_price = last_row['Close']
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Short-term Trend", trend_direction)
    m2.metric("Target Price", f"₹{prediction:.2f}", f"{((prediction/curr_price)-1)*100:.2f}%")
    m3.metric("RSI Level", f"{last_row['RSI']:.1f}")

    # Confidence Logic
    is_high_vol = last_row['Volume'] > last_row['Vol_SMA']
    confidence = "HIGH CONFIDENCE" if is_high_vol else "WEAK/FAKING"
    
    if last_row['Buy_S']:
        st.success(f"🚀 SIGNAL: BUY | Strength: {confidence}")
    elif last_row['Sell_S']:
        st.error(f"⚠️ SIGNAL: SELL | Strength: {confidence}")
    else:
        st.info(f"⚖️ MARKET STATUS: NEUTRAL | No Immediate Signal")

    # Export Button
    st.divider()
    csv_data = df.to_csv().encode('utf-8')
    st.download_button("📥 Download Full Analysis (CSV)", csv_data, f"{symbol}_analysis.csv", "text/csv")
