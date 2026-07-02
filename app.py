import pandas as pd

def price_storage_contract(injection_dates, withdrawal_dates, prices_df, 
                           rate, max_volume, storage_cost_per_day):
    prices_df['Date'] = pd.to_datetime(prices_df['Date'])
    price_map = prices_df.set_index('Date')['Price'].to_dict()
    
    events = []
    for d in injection_dates: events.append((pd.to_datetime(d), 'inject'))
    for d in withdrawal_dates: events.append((pd.to_datetime(d), 'withdraw'))
    events.sort(key=lambda x: x[0])

    current_volume = 0.0
    cashflow = 0.0

    for date, action in events:
        if date not in price_map: 
            continue
        price = price_map[date]
        if action == 'inject':
            amt = min(rate, max_volume - current_volume)
            cashflow -= amt * price
            current_volume += amt
        elif action == 'withdraw':
            amt = min(rate, current_volume)
            cashflow += amt * price
            current_volume -= amt

    if len(events) > 1:
        total_days = (events[-1][0] - events[0][0]).days + 1
        cashflow -= total_days * current_volume * storage_cost_per_day
    
    return round(cashflow, 2)


# === THIS IS THE PART YOU ADD ===
if __name__ == "__main__":
    # 1. Load your downloaded data
    df = pd.read_csv('gas_prices.csv') 
    df['Date'] = pd.to_datetime(df['Date'])

    # 2. Pick sample dates from your data. Example: Buy Jan, Sell Dec
    sample_inject = ['2020-01-02'] 
    sample_withdraw = ['2020-12-01'] 

    # 3. Run the function
    value = price_storage_contract(
        injection_dates=sample_inject,
        withdrawal_dates=sample_withdraw,
        prices_df=df,
        rate=100, # 100 Bcf/day
        max_volume=100, # 100 Bcf tank
        storage_cost_per_day=0.01 # $0.01 per Bcf/day
    )
    print("Sample Contract Value: $", value)
