import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="JPM Gas Storage Pricing", layout="wide")

# ========== 1. DATA LOADING - FIXES PATH + COLUMN ERRORS ==========
@st.cache_data
def load_data():
    """Loads gas_prices.csv and auto-maps Forage column names"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, "gas_prices.csv")
    
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}. Upload gas_prices.csv to GitHub.")
        st.stop()
        
    df = pd.read_csv(file_path)
    
    # Clean column names: make lowercase, remove spaces
    df.columns = [c.strip().lower() for c in df.columns]
    
    # Forage file uses 'observation date' and 'value'. Map to 'date', 'price'
    if 'observation date' in df.columns and 'value' in df.columns:
        df = df.rename(columns={'observation date': 'date', 'value': 'price'})
    elif 'date' in df.columns and 'price' in df.columns:
        pass # already correct
    else:
        st.error(f"CSV must have Date+Price or Observation Date+Value columns. Found: {df.columns.tolist()}")
        st.stop()
        
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return df

df = load_data()

# ========== 2. CORE PRICING LOGIC ==========
def price_storage_contract(injection_dates, withdrawal_dates, prices_df, 
                           rate, max_volume, storage_cost_per_day):
    """
    Prices a natural gas storage contract.
    Constraints: rate, max_volume, storage_cost. Assumes interest=0, no delay.
    """
    price_map = prices_df.set_index('date')['price'].to_dict()
    
    events = []
    for d in injection_dates:
        events.append((pd.to_datetime(d), 'inject'))
    for d in withdrawal_dates:
        events.append((pd.to_datetime(d), 'withdraw'))
    events.sort(key=lambda x: x[0])

    if not events:
        return 0.0, pd.DataFrame()

    current_volume = 0.0
    cashflow = 0.0
    log = [] # for day-by-day storage cost

    for date, action in events:
        if date not in price_map: 
            st.warning(f"No price data for {date.date()}, skipping.")
            continue
        
        price = price_map[date]
        
        if action == 'inject':
            amt = min(rate, max_volume - current_volume) # rate + capacity constraint
            cashflow -= amt * price
            current_volume += amt
            log.append([date, 'Inject', amt, price, -amt*price, current_volume])
            
        elif action == 'withdraw':
            amt = min(rate, current_volume) # rate + can't go negative
            cashflow += amt * price
            current_volume -= amt
            log.append([date, 'Withdraw', amt, price, amt*price, current_volume])

    # Storage cost: charge for every day you held gas
    if len(events) > 1:
        start_date, end_date = events[0][0], events[-1][0]
        all_dates = pd.date_range(start_date, end_date)
        total_storage_cost = 0
        vol = 0
        event_dict = {e[0]: e[1] for e in events}
        
        for d in all_dates:
            if d in event_dict:
                if event_dict[d] == 'inject': vol += min(rate, max_volume - vol)
                if event_dict[d] == 'withdraw': vol -= min(rate, vol)
            total_storage_cost += vol * storage_cost_per_day
            
        cashflow -= total_storage_cost
        log.append([end_date, 'Storage Cost', '', -total_storage_cost, vol])
    
    return round(cashflow, 2), pd.DataFrame(log, columns=['Date', 'Action', 'Bcf', 'Price', 'Cashflow', 'Volume End'])

# ========== 3. STREAMLIT UI ==========
st.title("JPMorgan Forage: Gas Storage Contract Pricer")
st.write(f"Loaded {len(df)} days of gas data: {df['date'].min().date()} to {df['date'].max().date()}")

col1, col2 = st.columns(2)
with col1:
    inject_dates_str = st.text_area("Injection Dates YYYY-MM-DD, comma sep", "2020-01-02")
    rate = st.number_input("Max Rate Bcf/day", min_value=1, value=100)
    max_vol = st.number_input("Max Volume Bcf", min_value=1, value=100)
with col2:
    withdraw_dates_str = st.text_area("Withdrawal Dates YYYY-MM-DD, comma sep", "2020-12-01")
    storage_cost = st.number_input("Storage Cost $/Bcf/day", min_value=0.0, value=0.01, format="%.4f")

if st.button("Price Contract"):
    inject_dates = [d.strip() for d in inject_dates_str.split(",") if d.strip()]
    withdraw_dates = [d.strip() for d in withdraw_dates_str.split(",") if d.strip()]
    
    value, log_df = price_storage_contract(inject_dates, withdraw_dates, df, rate, max_vol, storage_cost)
    
    st.metric(label="Total Contract P&L", value=f"${value:,.2f}")
    st.dataframe(log_df, use_container_width=True)
    st.line_chart(df.set_index('date')['price'])
