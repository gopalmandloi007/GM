import streamlit as st
import pandas as pd

def parse_holdings(json_response):
    """Convert API JSON to clean Pandas DataFrame"""
    data = json_response.get("data", [])
    parsed = []

    for item in data:
        for ts in item.get("tradingsymbol", []):
            parsed.append({
                "Exchange": ts.get("exchange"),
                "Symbol": ts.get("tradingsymbol"),
                "ISIN": ts.get("isin"),
                "DP Qty": item.get("dp_qty"),
                "T1 Qty": item.get("t1_qty"),
                "Trade Qty": item.get("trade_qty"),
                "Holding Used": item.get("holding_used"),
                "Avg Buy Price": item.get("avg_buy_price"),
                "Sell Amount": item.get("sell_amt"),
                "Haircut": item.get("haircut")
            })

    return pd.DataFrame(parsed)


# Example use inside Streamlit app
st.subheader("📊 My Holdings")

# json_response = call_your_api()  # <-- Replace with actual API call
# For testing, paste your sample JSON here:
json_response = {
"status":"SUCCESS",
"data":[
    {
        "dp_qty":"320","collateral_qty":"0","t1_qty":"0","holding_used":"320",
        "avg_buy_price":"312.00","haircut":"1.00","sell_amt":"97264.000000","trade_qty":"320",
        "tradingsymbol":[
            {"exchange":"NSE","tradingsymbol":"HINDWAREAP-EQ","token":"15883","price_precision":"2","ticksize":"0.05","lotsize":"1","isin":"INE05AN01011"},
            {"exchange":"BSE","tradingsymbol":"HINDWAREAP","token":"542905","price_precision":"2","ticksize":"0.05","lotsize":"1","isin":"INE05AN01011"}
        ]
    },
    {
        "dp_qty":"137","collateral_qty":"0","t1_qty":"0","holding_used":"0",
        "avg_buy_price":"181.80","haircut":"1.00","sell_amt":"0.000000","trade_qty":"0",
        "tradingsymbol":[
            {"exchange":"NSE","tradingsymbol":"GARUDA-EQ","token":"25800","price_precision":"2","ticksize":"0.01","lotsize":"1","isin":"INE0JVO01026"},
            {"exchange":"BSE","tradingsymbol":"GARUDA","token":"544271","price_precision":"2","ticksize":"0.05","lotsize":"1","isin":"INE0JVO01026"}
        ]
    }
]
}

df = parse_holdings(json_response)

# Show nice table
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)
