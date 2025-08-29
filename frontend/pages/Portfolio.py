# gm/frontend/pages/Portfolio.py
import streamlit as st
import pandas as pd
import json

def safe_json_load(s):
    """Safely load JSON string"""
    try:
        return json.loads(s) if isinstance(s, str) else s
    except Exception as e:
        st.write("❌ JSON parse error:", s, e)
        return None

def show_portfolio():
    st.title("📊 Portfolio")

    client = st.session_state.get("client")

    if not client:
        st.warning("⚠️ Please login first from the Login page.")
        return

    try:
        raw_holdings = client.get_holdings()

        st.write("🔍 Raw holdings from API:", raw_holdings)  # 👈 debug

        if not raw_holdings:
            st.info("No holdings found.")
            return

        holdings_list = []
        for h in raw_holdings:
            parsed = safe_json_load(h)
            if not parsed:
                continue  # skip invalid/empty entries

            ts = {}
            if isinstance(parsed.get("tradingsymbol"), list) and len(parsed["tradingsymbol"]) > 0:
                ts = next((t for t in parsed["tradingsymbol"] if t.get("exchange") == "NSE"), parsed["tradingsymbol"][0])

            holdings_list.append({
                "Symbol": ts.get("tradingsymbol", ""),
                "Exchange": ts.get("exchange", ""),
                "ISIN": ts.get("isin", ""),
                "Qty": parsed.get("dp_qty", "0"),
                "Used Qty": parsed.get("holding_used", "0"),
                "Buy Price": parsed.get("avg_buy_price", "0"),
                "Sell Amount": parsed.get("sell_amt", "0"),
                "Haircut": parsed.get("haircut", "0"),
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
