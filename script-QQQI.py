import os
import requests
import datetime
import pandas as pd
import shutil
import re
import json

DATA_FOLDER = "data/QQQI-Files"
EXCEL_URL = 'https://tinyurl.com/QQQI-Link'

def get_current_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def download_file(url, filename):
    response = requests.get(url)
    response.raise_for_status()
    with open(filename, 'wb') as file:
        file.write(response.content)

def parse_option_info(option_str):
    """
    Parse option ticker to get expiry date, option type, and strike price.
    Example: 'NDX 250919C23775000'
    """
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
    """
    Assign bucket based on the content of the ticker
    """
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
    pattern = re.compile(r"QQQI_.*_(\d{4}-\d{2}-\d{2})\.json")
    for filename in os.listdir(DATA_FOLDER):
        match = pattern.match(filename)
        if match:
            date_set.add(match.group(1))
    dates = sorted(date_set)
    available_dates = {"dates": dates}
    with open(os.path.join(DATA_FOLDER, "available_dates.json"), "w") as f:
        json.dump(available_dates, f, indent=2)
    print(f"Generated available_dates.json with dates: {dates}")

def main():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    date_str = get_current_date()
    excel_filename = os.path.join(DATA_FOLDER, f'QQQI_{date_str}.xlsx')

    # Download Excel if not already present
    if not os.path.exists(excel_filename):
        print(f"Downloading Excel file for {date_str}...")
        download_file(EXCEL_URL, excel_filename)
    else:
        print("File already downloaded.")

    # Read relevant columns from Excel
    df = pd.read_excel(excel_filename, header=None, usecols="E,G,H,I", skiprows=2)
    df.columns = ['Ticker', 'Price', 'BaseMV', 'Weight']
    df = df.dropna(subset=['Ticker', 'Weight'])

    # Assign bucket based on ticker content
    df['Bucket'] = df['Ticker'].apply(assign_bucket_from_ticker)

    # Total portfolio Base Market Value
    total_base_mv = df['BaseMV'].sum()

    # Hardcoded underlying price for options calculations
    opening_price = 23433

    # Process each bucket
    for bucket_name in ["Options - Index", "Cash", "Stocks"]:
        subset = df[df['Bucket'] == bucket_name].copy()

        if bucket_name == "Options - Index" and not subset.empty:
            # Parse option info
            subset[['Expiry_Date', 'Option_Type', 'Strike_Price']] = subset['Ticker'].apply(
                lambda val: pd.Series(parse_option_info(val))
            )

            # Calculate contracts (negative for short positions)
            subset['Contracts'] = -subset['BaseMV'] / subset['Price']

            # Forgone gain (only if underlying > strike)
            subset['ForgoneGain'] = ((opening_price - subset['Strike_Price']) * subset['Contracts']).where(
                opening_price > subset['Strike_Price'], 0
            )

            # % of total portfolio
            subset['ForgoneGainPct'] = subset['ForgoneGain'] / total_base_mv

            # Formatting for JSON
            subset['Weight'] = (subset['Weight'] * 100).map(lambda x: f"{x:.2f}")
            subset['Strike_Price'] = subset['Strike_Price'].map(lambda x: f"{x:,.2f}")
            subset['OpeningPrice'] = opening_price
            subset['Contracts'] = subset['Contracts'].map(lambda x: f"{x:,.2f}")
            subset['ForgoneGain'] = subset['ForgoneGain'].map(lambda x: f"{x:,.2f}")
            subset['ForgoneGainPct'] = subset['ForgoneGainPct'].map(lambda x: f"{x:.6f}")

            subset = subset[['Ticker', 'Weight', 'Expiry_Date', 'Option_Type', 'Strike_Price',
                             'OpeningPrice', 'Contracts', 'ForgoneGain', 'ForgoneGainPct']]

        elif bucket_name != "Options - Index" and not subset.empty:
            # For Cash or Stocks
            subset['Weight'] = (subset['Weight'] * 100).map(lambda x: f"{x:.2f}")
            subset = subset[['Ticker', 'Weight']]

        # Save JSON if any records exist
        if not subset.empty:
            filename = os.path.join(DATA_FOLDER, f'QQQI_{bucket_name.replace(" ", "_")}_{date_str}.json')
            subset.to_json(filename, orient="records")
            print(f"Saved {len(subset)} records to {filename}")
        else:
            print(f"No records found for bucket '{bucket_name}'.")

        # Copy dated JSON to "latest"
        latest_file = os.path.join(DATA_FOLDER, f'QQQI_{bucket_name.replace(" ", "_")}_latest.json')
        if not subset.empty:
            shutil.copyfile(filename, latest_file)
            print(f"Copied {filename} to {latest_file}")

    # Generate available dates JSON
    generate_available_dates_json()

if __name__ == '__main__':
    main()
