import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(layout="wide", page_title="India Alpha Analyzer")
st.title("🚀 India Alpha: Advanced Stock Analyzer")

# 1. Inputs
symbol = st.sidebar.text_input("NSE Ticker (e.g. SBIN.NS, TATAMOTORS.NS)", "SBIN.NS")
period = st.sidebar.selectbox("Analysis Horizon", ["1y", "2y", "5y"], index=0)

# 2. Data Engine
@st.cache_data
def get_data(ticker, pd_val):
    data = yf.download(ticker, period=pd_val, interval="1d")
    # FIX: Flatten Multi-Index columns from yfinance
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

df = get_data(symbol, period)

# 3. Indicator Calculations
df['SMA50'] = ta.sma(df['Close'], length=50)
df['SMA200'] = ta.sma(df['Close'], length=200)
df['RSI'] = ta.rsi(df['Close'], length=14)
bb = ta.bbands(df['Close'], length=20, std=2)
df = pd.concat([df, bb], axis=1).copy()

# 4. Signal Logic
def get_signal(row):
    lower_band = next((row[c] for c in row.index if 'BBL' in c), None)
    upper_band = next((row[c] for c in row.index if 'BBU' in c), None)
    
    if lower_band is not None and row['Close'] < lower_band and row['RSI'] < 35:
        return "BUY (Oversold Dip)"
    elif upper_band is not None and row['Close'] > upper_band and row['RSI'] > 70:
        return "SELL (Overbought Peak)"
    else:
        return "NEUTRAL"

df['Signal'] = df.apply(get_signal, axis=1)

# 5. Visualization
fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                    vertical_spacing=0.05, 
                    subplot_titles=('Price & BBands', 'Volume', 'RSI'),
                    row_heights=[0.5, 0.2, 0.3])

fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

if not df.filter(like='BBU').empty:
    fig.add_trace(go.Scatter(x=df.index, y=df.filter(like='BBU').iloc[:,0], line=dict(color='rgba(173, 216, 230, 0.4)'), name='Upper Band'), row=1, col=1)
if not df.filter(like='BBL').empty:
    fig.add_trace(go.Scatter(x=df.index, y=df.filter(like='BBL').iloc[:,0], fill='tonexty', line=dict(color='rgba(173, 216, 230, 0.4)'), name='Lower Band'), row=1, col=1)

fig.add_trace(go.Scatter(x=df.index, y=df['SMA200'], line=dict(color='yellow', width=2), name='200 SMA'), row=1, col=1)

# Color logic for volume bars
colors = ['green' if df['Open'].iloc[i] < df['Close'].iloc[i] else 'red' for i in range(len(df))]
fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)

fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name='RSI'), row=3, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

fig.update_layout(height=900, template="plotly_dark", showlegend=False, xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

# 6. Recommendation Dashboard
st.subheader("Current Market Verdict")
last_row = df.iloc[-1]
signal_text = last_row['Signal']
status_color = "green" if "BUY" in signal_text else "red" if "SELL" in signal_text else "white"
st.markdown(f"### Signal: :{status_color}[{signal_text}]")
