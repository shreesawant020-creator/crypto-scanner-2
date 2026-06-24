import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="Crypto Intelligence System", layout="wide")

binance = ccxt.binance()
kraken = ccxt.kraken()

st.title("📊 Crypto Intelligence System (Clean Version)")


# =============================
# SETTINGS
# =============================
timeframe = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m"])
min_score = st.sidebar.slider("Min Score", 0, 100, 0)

if "alert_memory" not in st.session_state:
    st.session_state.alert_memory = {}


# =============================
# MARKET DATA
# =============================
@st.cache_data(ttl=10)
def get_tickers():
    data = []
    tickers = binance.fetch_tickers()

    for s, t in tickers.items():
        if "/USDT" not in s:
            continue

        try:
            price = t.get("last")
            change = t.get("percentage")
            volume = t.get("quoteVolume")

            if price is None or change is None or volume is None:
                continue

            score = abs(change) * 2 + min(volume / 1_000_000, 50)

            data.append({
                "Symbol": s,
                "Price": price,
                "Change %": change,
                "Volume": volume,
                "Score": score
            })

        except:
            continue

    df = pd.DataFrame(data)
    return df.sort_values("Score", ascending=False)


# =============================
# OHLCV DATA
# =============================
@st.cache_data(ttl=10)
def ohlcv(symbol):
    try:
        data = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=80)

        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume"
        ])

        df["time"] = pd.to_datetime(df["time"], unit="ms")
        return df

    except:
        return None


# =============================
# AI STYLE SIGNAL ENGINE
# =============================
def ai_signal(df):

    close = df["close"]
    volume = df["volume"]

    price = close.iloc[-1]

    resistance = df["high"].rolling(20).max().iloc[-1]
    support = df["low"].rolling(20).min().iloc[-1]

    avg_vol = volume.rolling(20).mean().iloc[-1]
    last_vol = volume.iloc[-1]

    score = 0

    # breakout pressure
    if price > resistance * 0.99:
        score += 35

    # volume spike
    if last_vol > avg_vol * 1.3:
        score += 25

    # trend
    if close.iloc[-1] > close.iloc[-10]:
        score += 20

    # momentum
    if close.pct_change().iloc[-1] > 0:
        score += 10

    # volatility filter
    if close.pct_change().std() > 0.06:
        score -= 10

    if score < min_score:
        return None

    if score >= 70:
        signal = "🟢 STRONG"
    elif score >= 40:
        signal = "🟡 WATCH"
    else:
        signal = "🔴 WEAK"

    return score, signal, support, resistance


# =============================
# BACKTEST ENGINE
# =============================
def backtest(symbol):

    df = ohlcv(symbol)
    if df is None:
        return None

    wins, losses = 0, 0

    for i in range(20, len(df) - 2):

        window = df.iloc[i-20:i]

        resistance = window["high"].max()
        price = df["close"].iloc[i]
        future = df["close"].iloc[i+1]

        if price > resistance * 0.99:
            if future > price:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    if total == 0:
        return None

    return wins, losses, (wins / total) * 100


# =============================
# ARBITRAGE SCANNER
# =============================
def arbitrage(symbol):

    try:
        b_price = binance.fetch_ticker(symbol)["last"]

        k_symbol = symbol.replace("/USDT", "/USD")
        k_price = kraken.fetch_ticker(k_symbol)["last"]

        return abs(b_price - k_price)

    except:
        return None


# =============================
# MAIN DATA
# =============================
df = get_tickers()

if df.empty:
    st.warning("Market data temporarily unavailable. Please refresh.")
    st.stop()s

if df.empty:
    st.error("No market data")
    st.stop()


col1, col2 = st.columns([2, 1])


# =============================
# TABLE
# =============================
with col1:
    st.subheader("📊 Market Scanner")
    st.dataframe(df, use_container_width=True)


# =============================
# ANALYSIS PANEL
# =============================
with col2:

    symbol = st.selectbox("Select Coin", df["Symbol"].head(50))

    data = ohlcv(symbol)

    if data is not None:

        res = ai_signal(data)

        if res:

            score, signal, support, resistance = res

            st.metric("Score", round(score, 2))
            st.markdown(f"### {signal}")

            st.write("Support:", support)
            st.write("Resistance:", resistance)

            st.subheader("📈 Price")
            st.line_chart(data.set_index("time")["close"])

            st.subheader("📊 Volume")
            st.bar_chart(data.set_index("time")["volume"])

            # BACKTEST
            bt = backtest(symbol)
            if bt:
                w, l, wr = bt
                st.subheader("🧪 Backtest")
                st.write(f"Winrate: {wr:.2f}% ({w}/{l})")

            # ARBITRAGE
            arb = arbitrage(symbol)
            if arb:
                st.subheader("💱 Arbitrage")
                st.write("Price Difference:", arb)

        else:
            st.warning("No strong signal")