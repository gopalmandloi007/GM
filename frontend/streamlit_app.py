import streamlit as st
from trading_engine import SessionManager, OrderManager, WebSocketManager, MarketDataService, set_default_client
from trading_engine import get_default_client
import trading_engine as te
import time

st.set_page_config(page_title='Definedge Demo', layout='wide')

st.title('Definedge Trading Engine - Demo (Use carefully)')

# Secrets (store in .streamlit/secrets.toml or set env vars)
api_token = st.secrets.get('DEFINEDGE_API_TOKEN') or st.text_input('API token', value='', type='default')
api_secret = st.secrets.get('DEFINEDGE_API_SECRET') or st.text_input('API secret', value='', type='password')
totp_secret = st.secrets.get('DEFINEDGE_TOTP_SECRET') or st.text_input('TOTP secret (optional)', value='', type='password')

if 'client' not in st.session_state:
    st.session_state['client'] = None
if 'ws' not in st.session_state:
    st.session_state['ws'] = None

col1, col2 = st.columns([1,2])

with col1:
    st.header('Session')
    if st.button('Create Session'):
        if not api_token or not api_secret:
            st.error('Provide API token and secret (via secrets or inputs)')
        else:
            try:
                sm = SessionManager(api_token=api_token, api_secret=api_secret, totp_secret=(totp_secret or None))
                client = sm.create_session()
                st.session_state['client'] = client
                set_default_client(client)
                st.success('Session created.')
                st.write({'uid': client.uid, 'susertoken': client.susertoken})
            except Exception as e:
                st.error(f'Login failed: {e}')

    if st.session_state['client']:
        if st.button('Start WebSocket'):
            client = st.session_state['client']
            ws = WebSocketManager(uid=client.uid, actid=client.uid, susertoken=client.susertoken)
            ws.start()
            st.session_state['ws'] = ws
            st.success('WebSocket started (check logs).')

        if st.session_state['ws']:
            if st.button('Stop WebSocket'):
                st.session_state['ws'].stop()
                st.session_state['ws'] = None
                st.success('WebSocket stopped.')

with col2:
    st.header('Quick Actions')
    client = st.session_state.get('client')
    if client:
        if st.button('Show Holdings'):
            try:
                holdings = client.get_holdings()
                st.write(holdings)
            except Exception as e:
                st.error(f'Error fetching holdings: {e}')
        if st.button('Show Positions'):
            try:
                pos = client.get_positions()
                st.write(pos)
            except Exception as e:
                st.error(f'Error fetching positions: {e}')

        st.markdown('---')
        st.subheader('Place Order (Demo)')
        tradingsymbol = st.text_input('Trading Symbol (e.g. RELIANCE)', value='RELIANCE')
        exchange = st.selectbox('Exchange', ['NSE','NFO','BSE'], index=0)
        qty = st.number_input('Quantity', value=1, min_value=1, step=1)
        side = st.selectbox('Side', ['BUY','SELL'], index=0)
        price_type = st.selectbox('Price Type', ['MARKET','LIMIT','SL','SL-M'], index=0)
        price = st.number_input('Price (0 for MARKET)', value=0.0, format='%.2f')
        trigger = st.number_input('Trigger Price (for SL)', value=0.0, format='%.2f')
        if st.button('Place Order (do not run on real account unless you intend)'):
            om = OrderManager(client)
            try:
                resp = om.place_order(
                    tradingsymbol=tradingsymbol,
                    exchange=exchange,
                    quantity=int(qty),
                    price_type=price_type,
                    side=side,
                    price=price if price > 0 else 0,
                    trigger_price=trigger if trigger > 0 else None
                )
                st.success('Order response (logged)')
                st.write(resp)
            except Exception as e:
                st.error(f'Order error: {e}')
    else:
        st.info('Create a session first to use actions.')

st.markdown('---')
st.caption('This is a demo UI. Use with caution. API calls may place real orders.')
