import streamlit as st
import pandas as pd
from kiteconnect import KiteConnect
from datetime import datetime, timedelta
from sector_universe import SECTOR_STOCKS

st.set_page_config(page_title="NSE Sector Scanner", layout="wide")

st.title("📊 NSE Sector & Stock Scanner")

api_key = st.text_input("Kite API Key")
access_token = st.text_input("Kite Access Token", type="password")

if st.button("Run Scanner"):

    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)

        instruments = kite.instruments("NSE")

        instrument_map = {
            item["tradingsymbol"]: item["instrument_token"]
            for item in instruments
        }

        results = []

        total_stocks = sum(len(stocks) for stocks in SECTOR_STOCKS.values())
        progress = st.progress(0)
        current = 0

        for sector, stocks in SECTOR_STOCKS.items():

            quote_symbols = [f"NSE:{stock}" for stock in stocks]

            try:
                quotes = kite.quote(quote_symbols)
            except Exception:
                continue

            for stock in stocks:

                current += 1
                progress.progress(current / total_stocks)

                try:
                    if stock not in instrument_map:
                        continue

                    quote_key = f"NSE:{stock}"

                    if quote_key not in quotes:
                        continue

                    q = quotes[quote_key]

                    last_price = q["last_price"]
                    close_price = q["ohlc"]["close"]
                    live_volume = q["volume"]

                    if close_price == 0:
                        continue

                    change_pct = ((last_price - close_price) / close_price) * 100

                    token = instrument_map[stock]

                    to_date = datetime.now()
                    from_date = to_date - timedelta(days=35)

                    candles = kite.historical_data(
                        instrument_token=token,
                        from_date=from_date,
                        to_date=to_date,
                        interval="day"
                    )

                    df = pd.DataFrame(candles)

                    if df.empty or len(df) < 20:
                        continue

                    last_20 = df.tail(20)

                    avg_volume = last_20["volume"].mean()
                    avg_turnover = (last_20["close"] * last_20["volume"]).mean()

                    turnover_today = last_price * live_volume

                    rvol = live_volume / avg_volume if avg_volume > 0 else 0
                    rturnover = turnover_today / avg_turnover if avg_turnover > 0 else 0

                    r_factor = 0

                    if change_pct > 1:
                        r_factor += 2
                    if change_pct > 2:
                        r_factor += 2
                    if change_pct < -1:
                        r_factor += 2
                    if change_pct < -2:
                        r_factor += 2

                    if rvol > 1.5:
                        r_factor += 3
                    if rvol > 2:
                        r_factor += 2

                    if rturnover > 1.5:
                        r_factor += 2
                    if rturnover > 2:
                        r_factor += 2

                    direction = "LONG" if change_pct > 0 else "SHORT"

                    results.append({
                        "Sector": sector,
                        "Stock": stock,
                        "Direction": direction,
                        "Change %": round(change_pct, 2),
                        "Volume": live_volume,
                        "RVOL": round(rvol, 2),
                        "RTurnover": round(rturnover, 2),
                        "R-Factor": r_factor
                    })

                except Exception:
                    continue

        if not results:
            st.warning("No results found.")
        else:
            result_df = pd.DataFrame(results)

            long_df = result_df[result_df["Direction"] == "LONG"]
            short_df = result_df[result_df["Direction"] == "SHORT"]

            st.subheader("📈 Strong Long Sectors")

            if not long_df.empty:
                long_sector = (
                    long_df.groupby("Sector")
                    .agg({
                        "R-Factor": "mean",
                        "Change %": "mean",
                        "RVOL": "mean",
                        "RTurnover": "mean",
                        "Stock": "count"
                    })
                    .reset_index()
                    .rename(columns={"Stock": "Active Stocks"})
                    .sort_values(by="R-Factor", ascending=False)
                )

                st.dataframe(long_sector, use_container_width=True)
            else:
                st.info("No long sectors found.")

            st.subheader("📉 Strong Short Sectors")

            if not short_df.empty:
                short_sector = (
                    short_df.groupby("Sector")
                    .agg({
                        "R-Factor": "mean",
                        "Change %": "mean",
                        "RVOL": "mean",
                        "RTurnover": "mean",
                        "Stock": "count"
                    })
                    .reset_index()
                    .rename(columns={"Stock": "Active Stocks"})
                    .sort_values(by="R-Factor", ascending=False)
                )

                st.dataframe(short_sector, use_container_width=True)
            else:
                st.info("No short sectors found.")

            st.subheader("🚀 Top Stocks")

            top_stocks = result_df.sort_values(
                by="R-Factor",
                ascending=False
            )

            st.dataframe(top_stocks, use_container_width=True)

            st.success("Scanner completed successfully.")

    except Exception as e:
        st.error(str(e))