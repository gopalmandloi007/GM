import streamlit as st
from GM.backend.holdings import get_holdings

st.title("Portfolio")

uid = st.text_input("Enter UID")
if st.button("Fetch Holdings"):
    data = get_holdings(uid)
    if data:
        st.json(data)
    else:
        st.error("No holdings found.")
