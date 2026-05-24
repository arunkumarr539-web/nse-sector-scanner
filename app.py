result_df = pd.DataFrame(results)

# Keep only active stocks
active_df = result_df[result_df["R-Factor"] > 0]

if active_df.empty:
    st.warning("No high activity stocks found.")
else:
    # Find strongest sectors first
    sector_strength = (
        active_df.groupby(["Sector", "Direction"])
        .agg({
            "R-Factor": "mean",
            "Turnover Cr": "sum",
            "Stock": "count"
        })
        .reset_index()
        .rename(columns={"Stock": "Active Stocks"})
        .sort_values(by="R-Factor", ascending=False)
    )

    # Pick top 3 strongest sectors only
    top_sectors = sector_strength.head(3)["Sector"].tolist()

    # Show only stocks from strongest sectors
    top_active_stocks = (
        active_df[active_df["Sector"].isin(top_sectors)]
        .sort_values(
            by=["R-Factor", "Turnover Cr"],
            ascending=False
        )
        .head(20)
    )

    st.subheader("🔥 Top Active Stocks From Strong Sectors")

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