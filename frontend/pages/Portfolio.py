import json
import re
import streamlit as st
import pandas as pd


# --- Fix JSON issues before parsing ---
def safe_json_load(s):
    if isinstance(s, dict):
        return s
    if not isinstance(s, str):
        return {}

    # Clean common JSON errors
    s = s.strip()
    s = re.sub(r'("status":"SUCCESS")\s*("data")', r'\1,\2', s)  # add missing comma
    s = re.sub(r'(\d+):', r'"\1":', s)  # convert 0: -> "0":
    s = s.replace("\n", "")  # remove newlines

    try:
        return json.loads(s)
    except Exception as e:
        st.error(f"❌ JSON parse error: {e}")
        st.code(s, language="json")
        return {}


# --- Streamlit Page ---
st.title("📊 Portfolio")

# Dummy: replace with your API call
raw_response = st.session_state.get("raw_holdings", None)

if raw_response:
    holdings_data = safe_json_load(raw_response)

    if holdings_data.get("status") == "SUCCESS" and "data" in holdings_data:
        data = holdings_data["data"]

        # Flatten portfolio for DataFrame
        rows = []
        for item in data.values() if isinstance(data, dict) else data:
            qty = int(item.get("dp_qty", 0))
            avg_price = float(item.get("avg_buy_price", 0))
            symbol = item.get("tradingsymbol", [{}])[0].get("tradingsymbol", "")

            rows.append({
                "Symbol": symbol,
                "Quantity": qty,
                "Avg Buy Price": avg_price,
                "Holding Used": item.get("holding_used", 0),
                "Sell Amount": float(item.get("sell_amt", 0))
            })

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("⚠️ No valid holdings to display.")
    else:
        st.warning("⚠️ No valid holdings to display.")
else:
    st.info("ℹ️ No raw holdings found in session. Please fetch from API.")
