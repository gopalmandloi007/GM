# gm/frontend/pages/Portfolio.py
import streamlit as st
import pandas as pd
import json

def show_portfolio():
    st.title("📊 Portfolio")

    client = st.session_state.get("client")

    if not client:
        st.warning("⚠️ Please login first from the Login page.")
        return

    try:
        raw_holdings = client.get_holdings()

        if not raw_holdings:
            st.info("No holdings found.")
            return

        # Parse each holding JSON string into dict
        holdings_list = []
        for h in raw_holdings:
            if isinstance(h, str):  # convert string to dict
                h = json.loads(h)

            # Take first tradingsymbol (NSE preferred)
            ts = h.get("tradingsymbol", [{}])[0]

            holdings_list.append({
                "Symbol": ts.get("tradingsymbol", ""),
                "Exchange": ts.get("exchange", ""),
                "ISIN": ts.get("isin", ""),
                "Qty": h.get("dp_qty", "0"),
                "Used Qty": h.get("holding_used", "0"),
                "Buy Price": h.get("avg_buy_price", "0"),
                "Sell Amount": h.get("sell_amt", "0"),
                "Haircut": h.get("haircut", "0"),
            })

        # Convert to DataFrame
        df = pd.DataFrame(holdings_list)

        st.success("Holdings fetched successfully ✅")
        st.dataframe(df)

    except Exception as e:
        st.error(f"Failed to fetch holdings: {e}")

if __name__ == "__main__":
    show_portfolio()
