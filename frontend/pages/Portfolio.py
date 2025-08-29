# gm/frontend/pages/Portfolio.py
import streamlit as st
import pandas as pd
import json

def safe_json_load(s):
    """Safely load JSON string"""
    try:
        return json.loads(s) if isinstance(s, str) else s
    except Exception:
        return None

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

        holdings_list = []
        for h in raw_holdings:
            h = safe_json_load(h)
            if not h:
                continue  # skip invalid/empty entries

            ts = {}
            if isinstance(h.get("tradingsymbol"), list) and len(h["tradingsymbol"]) > 0:
                # prefer NSE
                ts = next((t for t in h["tradingsymbol"] if t.get("exchange") == "NSE"), h["tradingsymbol"][0])

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

        if not holdings_list:
            st.info("⚠️ No valid holdings to display.")
            return

        df = pd.DataFrame(holdings_list)

        st.success("Holdings fetched successfully ✅")
        st.dataframe(df)

    except Exception as e:
        st.error(f"Failed to fetch holdings: {e}")

if __name__ == "__main__":
    show_portfolio()
