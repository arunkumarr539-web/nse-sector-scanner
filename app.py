import streamlit as st
import pandas as pd
from kiteconnect import KiteConnect
from datetime import datetime, timedelta
from sector_universe import SECTOR_STOCKS

st.set_page_config(page_title="NSE Sector Scanner", layout="wide")

st.title("📊 NSE Strong Sector Active Stock Scanner")

api_key = st.text_input("Kite API Key")
access_token = st.text_input("Kite Access Token", type="password")


def calculate_spread(q):
    try:
        buy = q["depth"]["buy"][0]["price"]
        sell = q["depth"]["sell"][0]["price"]

        if buy == 0 or sell == 0:
            return None

        return round(((sell - buy) / buy) * 100, 3)
    except Exception:
        return None


def get_current_month_futures_map(kite):
    instruments = kite.instruments("NFO")
    today = datetime.now().date()
    futures = {}

    for item in instruments:
        if item["instrument_type"] == "FUT" and item["expiry"] >= today:
            name = item["name"]

            if name not in futures:
                futures[name] = item
            elif item["expiry"] < futures[name]["expiry"]:
                futures[name] = item

    return futures


def get_20d_cash_data(kite, token):
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
        return None, None

    last_20 = df.tail(20)

    avg_volume = last_20["volume"].mean()
    avg_turnover = (last_20["close"] * last_20["volume"]).mean()

    return avg_volume, avg_turnover


def get_20d_fut_oi(kite, fut_token):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=35)

    candles = kite.historical_data(
        instrument_token=fut_token,
        from_date=from_date,
        to_date=to_date,
        interval="day",
        oi=True
    )

    df = pd.DataFrame(candles)

    if df.empty or "oi" not in df.columns or len(df) < 20:
        return 0

    return df.tail(20)["oi"].mean()


def calculate_r_factor(change_pct, rvol, rturnover, oi_ratio, spread):
    r_factor = 0

    # Price strength
    if change_pct > 1:
        r_factor += 2
    if change_pct > 2:
        r_factor += 2
    if change_pct < -1:
        r_factor += 2
    if change_pct < -2:
        r_factor += 2

    # Volume strength
    if rvol > 1.5:
        r_factor += 3
    if rvol > 2:
        r_factor += 2
    if rvol > 3:
        r_factor += 2

    # Turnover strength
    if rturnover > 1.5:
        r_factor += 2
    if rturnover > 2:
        r_factor += 2
    if rturnover > 3:
        r_factor += 2

    # Futures OI strength
    if oi_ratio > 1.2:
        r_factor += 2
    if oi_ratio > 1.5:
        r_factor += 2
    if oi_ratio > 2:
        r_factor += 2

    # Spread quality
    if spread is not None and spread < 0.15:
        r_factor += 2
    elif spread is not None and spread > 0.5:
        r_factor -= 2

    return r_factor


if st.button("Run Scanner"):

    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)

        st.info("Fetching NSE instruments...")
        nse_instruments = kite.instruments("NSE")

        instrument_map = {
            item["tradingsymbol"]: item["instrument_token"]
            for item in nse_instruments
        }

        st.info("Fetching futures instruments...")
        futures_map = get_current_month_futures_map(kite)

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
                    avg_price = q["average_price"]

                    if close_price == 0:
                        continue

                    change_pct = ((last_price - close_price) / close_price) * 100

                    avg_volume, avg_turnover = get_20d_cash_data(
                        kite,
                        instrument_map[stock]
                    )

                    if avg_volume is None or avg_turnover is None:
                        continue

                    turnover_today = avg_price * live_volume
                    turnover_cr = turnover_today / 10000000

                    rvol = live_volume / avg_volume if avg_volume > 0 else 0
                    rturnover = turnover_today / avg_turnover if avg_turnover > 0 else 0

                    spread = calculate_spread(q)

                    fut_oi = 0
                    oi_ratio = 0

                    if stock in futures_map:
                        fut_item = futures_map[stock]
                        fut_symbol = f"NFO:{fut_item['tradingsymbol']}"

                        try:
                            fut_quote = kite.quote(fut_symbol)[fut_symbol]
                            fut_oi = fut_quote.get("oi", 0)

                            avg_oi_20 = get_20d_fut_oi(
                                kite,
                                fut_item["instrument_token"]
                            )

                            oi_ratio = fut_oi / avg_oi_20 if avg_oi_20 > 0 else 0

                        except Exception:
                            pass

                    r_factor = calculate_r_factor(
                        change_pct,
                        rvol,
                        rturnover,
                        oi_ratio,
                        spread
                    )

                    direction = "LONG" if change_pct > 0 else "SHORT"

                    results.append({
                        "Sector": sector,
                        "Stock": stock,
                        "Direction": direction,
                        "Change %": round(change_pct, 2),
                        "Volume": live_volume,
                        "Turnover Cr": round(turnover_cr, 2),
                        "RVOL": round(rvol, 2),
                        "RTurnover": round(rturnover, 2),
                        "Futures OI": fut_oi,
                        "OI Ratio": round(oi_ratio, 2),
                        "Spread %": spread if spread is not None else "NA",
                        "R-Factor": r_factor
                    })

                except Exception:
                    continue

        if not results:
            st.warning("No results found.")

        else:
            result_df = pd.DataFrame(results)

            active_df = result_df[result_df["R-Factor"] > 0]

            if active_df.empty:
                st.warning("No high activity stocks found.")

            else:
                sector_strength = (
                    active_df.groupby(["Sector", "Direction"])
                    .agg({
                        "R-Factor": "mean",
                        "Turnover Cr": "sum",
                        "RVOL": "mean",
                        "RTurnover": "mean",
                        "OI Ratio": "mean",
                        "Stock": "count"
                    })
                    .reset_index()
                    .rename(columns={"Stock": "Active Stocks"})
                    .sort_values(by="R-Factor", ascending=False)
                )

                top_sectors = sector_strength.head(3)["Sector"].tolist()

                top_active_stocks = (
                    active_df[active_df["Sector"].isin(top_sectors)]
                    .sort_values(
                        by=["R-Factor", "Turnover Cr"],
                        ascending=False
                    )
                    .head(20)
                )

                st.subheader("🔥 Strong Sectors")

                st.dataframe(
                    sector_strength.head(5),
                    use_container_width=True
                )

                st.subheader("🚀 Top Active Stocks From Strong Sectors")

                st.dataframe(
                    top_active_stocks[
                        [
                            "Sector",
                            "Stock",
                            "Direction",
                            "Change %",
                            "RVOL",
                            "RTurnover",
                            "OI Ratio",
                            "Turnover Cr",
                            "Spread %",
                            "R-Factor"
                        ]
                    ],
                    use_container_width=True
                )

                st.success("Scanner completed successfully.")

    except Exception as e:
        st.error(str(e))