# frontend/pages/02_portfolio.py
import streamlit as st
import matplotlib.pyplot as plt
from trading_engine.portfolio import PortfolioManager
from trading_engine.session import SessionManager

def app():
    st.header("📊 Portfolio")
    if "api_client" not in st.session_state:
        st.info("Login first (open Login page).")
        return
    pm: PortfolioManager = st.session_state.portfolio_mgr
    if st.button("Refresh"):
        st.session_state.holdings_df = pm.fetch_holdings_table()
        st.session_state.positions_df = pm.fetch_positions_table()

    holdings = st.session_state.get("holdings_df") or pm.fetch_holdings_table()
    positions = st.session_state.get("positions_df") or pm.fetch_positions_table()
    summary = pm.portfolio_summary()

    cols = st.columns(4)
    cols[0].metric("Total Invested", f"₹ {summary['total_invested']:.2f}")
    cols[1].metric("Current Value", f"₹ {summary['total_current_value']:.2f}")
    cols[2].metric("Today P&L", f"₹ {summary['todays_pnl']:.2f}")
    cols[3].metric("Overall Unrealized", f"₹ {summary['overall_unrealized']:.2f}")

    st.subheader("Holdings")
    if holdings is None or holdings.empty:
        st.info("No holdings")
    else:
        st.dataframe(holdings, use_container_width=True)
        a,b = st.columns([1,1])
        with a:
            try:
                fig, ax = plt.subplots(figsize=(4,3))
                ax.pie(holdings["invested"].tolist(), labels=holdings["symbol"].tolist(), autopct='%1.1f%%', startangle=140)
                ax.axis('equal')
                st.pyplot(fig)
            except Exception as e:
                st.write("Pie chart error:", e)
        with b:
            try:
                fig2, ax2 = plt.subplots(figsize=(6,3))
                ax2.bar(holdings["symbol"].tolist(), holdings["overall_unrealized"].tolist())
                ax2.set_title("Unrealized P&L")
                ax2.set_ylabel("₹")
                plt.xticks(rotation=45, ha='right')
                st.pyplot(fig2)
            except Exception as e:
                st.write("Bar chart error:", e)

    st.subheader("Positions")
    if positions is None or positions.empty:
        st.info("No positions")
    else:
        st.dataframe(positions, use_container_width=True)
