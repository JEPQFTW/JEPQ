import os
import pandas as pd
import datetime
import json
import shutil

DATA_FOLDER = "data/QQQI-Files"
CSV_URL = 'https://tinyurl.com/QQQI-Link'  # Replace with your CSV URL if downloading

def get_current_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def parse_option_info(option_str):
    try:
        option_str = option_str.strip()
        parts = option_str.split()
        if len(parts) < 2:
            return None, None, None
        code = parts[1]
        date_code = code[:6]
        expiry_date = datetime.datetime.strptime(date_code, "%y%m%d").strftime("%Y-%m-%d")
        option_type = code[6]
        strike_raw = code[7:]
        strike_price = int(strike_raw) / 1000
        return expiry_date, option_type, strike_price
    except Exception:
        return None, None, None

def assign_bucket_from_ticker(ticker):
    if isinstance(ticker, str):
        if ticker.startswith("NDX"):
            return "Options - Index"
        elif ticker.startswith("Cash"):
            return "Cash"
        else:
            return "Stocks"
    return "Stocks"

def generate_available_dates_json():
    date_set = set()
    for filename in os.listdir(DATA_FOLDER):
        if filename.startswith("QQQI_") and filename.endswith(".json") and "latest" not in filename:
            parts = filename.split("_")
            date_str = parts[-1].replace(".json","")
            date_set.add(date_str)
    dates = sorted(date_set)
    available_dates = {"dates": dates}
    with open(os.path.join(DATA_FOLDER, "available_dates.json"), "w") as f:
        json.dump(available_dates, f, indent=2)
    print(f"Generated available_dates.json with dates: {dates}")

def main():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    date_str = get_current_date()
    csv_filename = os.path.join(DATA_FOLDER, f'QQQI_{date_str}.csv')

    # If CSV is already downloaded, skip. Otherwise you could download here.

    # Read CSV
    df = pd.read_csv(csv_filename, usecols=['StockTicker','Price','MarketValue','Weightings'])
    df = df.dropna(subset=['StockTicker', 'Weightings'])

    # Clean numeric columns
    df['Price'] = pd.to_numeric(df['Price'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce')
    df['MarketValue'] = pd.to_numeric(df['MarketValue'].astype(str).str.replace('$','').str.replace(',',''), errors='coerce')
    df['Weightings'] = pd.to_numeric(df['Weightings'].astype(str).str.replace('%','').str.replace(',',''), errors='coerce')
    df = df.dropna(subset=['Price','MarketValue'])

    # Assign bucket
    df['Bucket'] = df['StockTicker'].apply(assign_bucket_from_ticker)

    total_base_mv = df['MarketValue'].sum()
    opening_price = 23433  # Example hardcoded

    for bucket_name in ["Options - Index", "Cash", "Stocks"]:
        subset = df[df['Bucket'] == bucket_name].copy()
        if subset.empty:
            print(f"No records found for bucket '{bucket_name}'.")
            continue

        if bucket_name == "Options - Index":
            subset[['Expiry_Date', 'Option_Type', 'Strike_Price']] = subset['StockTicker'].apply(
                lambda val: pd.Series(parse_option_info(val))
            )
            subset['Contracts'] = -subset['MarketValue'] / subset['Price']
            subset['ForgoneGain'] = ((opening_price - subset['Strike_Price']) * subset['Contracts']).where(
                opening_price > subset['Strike_Price'], 0
            )
            subset['ForgoneGainPct'] = subset['ForgoneGain'] / total_base_mv

            subset['Weightings'] = subset['Weightings'].map(lambda x: f"{x:.2f}")
            subset['Strike_Price'] = subset['Strike_Price'].map(lambda x: f"{x:,.2f}")
            subset['OpeningPrice'] = opening_price
            subset['Contracts'] = subset['Contracts'].map(lambda x: f"{x:,.2f}")
            subset['ForgoneGain'] = subset['ForgoneGain'].map(lambda x: f"{x:,.2f}")
            subset['ForgoneGainPct'] = subset['ForgoneGainPct'].map(lambda x: f"{x:.6f}")

            subset = subset[['StockTicker', 'Weightings', 'Expiry_Date', 'Option_Type',
                             'Strike_Price', 'OpeningPrice', 'Contracts', 'ForgoneGain', 'ForgoneGainPct']]

        else:
            subset['Weightings'] = subset['Weightings'].map(lambda x: f"{x:.2f}")
            subset = subset[['StockTicker','Weightings']]

        filename = os.path.join(DATA_FOLDER, f'QQQI_{bucket_name.replace(" ","_")}_{date_str}.json')
        subset.to_json(filename, orient="records", indent=2)
        print(f"Saved {len(subset)} records to {filename}")

        latest_file = os.path.join(DATA_FOLDER, f'QQQI_{bucket_name.replace(" ","_")}_latest.json')
        shutil.copyfile(filename, latest_file)

    generate_available_dates_json()

if __name__ == '__main__':
    main()
