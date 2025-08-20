import os
import requests
import datetime
import pandas as pd
import shutil
import re
import json

DATA_FOLDER = "data"
EXCEL_URL = 'https://tinyurl.com/Pr0d1g10s0'

def get_current_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def download_file(url, filename):
    response = requests.get(url)
    response.raise_for_status()
    with open(filename, 'wb') as file:
        file.write(response.content)

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
        strike_price = int(strike_raw) / 1000  # numeric for calculations
        return expiry_date, option_type, strike_price
    except Exception:
        return None, None, None

def generate_available_dates_json():
    date_set = set()
    pattern = re.compile(r"JEPQ_.*_(\d{4}-\d{2}-\d{2})\.json")
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
    excel_filename = os.path.join(DATA_FOLDER, f'JEPQ_{date_str}.xlsx')

    if not os.path.exists(excel_filename):
        download_file(EXCEL_URL, excel_filename)
    else:
        print("file already downloaded.")

    # Read relevant columns
    df = pd.read_excel(excel_filename, header=None, usecols="A,B,C,F,G,H", skiprows=8)
    df.columns = ['Ticker_A', 'Ticker_B', 'Type', 'Weight', 'BaseMV', 'Price']
    df = df.dropna(subset=['Type', 'Weight'])

    # Assign bucket
    def assign_bucket(row):
        if row['Type'] == "Option - Index":
            return "Options - Index"
        elif row['Type'] == "Cash":
            return "Cash"
        else:
            return "Stocks"
    df['Bucket'] = df.apply(assign_bucket, axis=1)

    # Total portfolio Base Market Value (for % calculation)
    total_base_mv = df['BaseMV'].sum()

for bucket_name in ["Options - Index", "Cash", "Stocks"]:
    subset = df[df['Bucket'] == bucket_name].copy()

    if bucket_name == "Options - Index":
        subset['Ticker'] = subset['Ticker_B']
        subset[['Expiry_Date', 'Option_Type', 'Strike_Price']] = subset['Ticker_B'].apply(
            lambda val: pd.Series(parse_option_info(val))
        )

        opening_price = 23384  # hardcoded underlying price

        # Calculate Contracts
        subset['Contracts'] = -subset['BaseMV'] / subset['Price']

        # Calculate ForgoneGain only if OpeningPrice > Strike_Price
        subset['ForgoneGain'] = ((opening_price - subset['Strike_Price']) * subset['Contracts']).where(
            opening_price > subset['Strike_Price'], 0
        )

        # Calculate ForgoneGainPct
        subset['ForgoneGainPct'] = subset['ForgoneGain'] / total_base_mv


            # Format weight for JSON
            subset['Weight'] = (subset['Weight'] * 100).map(lambda x: f"{x:.2f}")

            # Format Strike_Price and numerical columns for JSON
            subset['Strike_Price'] = subset['Strike_Price'].map(lambda x: f"{x:,.2f}")
            subset['OpeningPrice'] = opening_price
            subset['Contracts'] = subset['Contracts'].map(lambda x: f"{x:,.2f}")
            subset['ForgoneGain'] = subset['ForgoneGain'].map(lambda x: f"{x:,.2f}")
            subset['ForgoneGainPct'] = subset['ForgoneGainPct'].map(lambda x: f"{x:.6f}")

            subset = subset[['Ticker', 'Weight', 'Expiry_Date', 'Option_Type', 'Strike_Price', 'OpeningPrice',
                             'Contracts', 'ForgoneGain', 'ForgoneGainPct']]
        else:
            subset['Ticker'] = subset['Ticker_A']
            subset['Weight'] = (subset['Weight'] * 100).map(lambda x: f"{x:.2f}")
            subset = subset[['Ticker', 'Weight']]

        # Save JSON
        if not subset.empty:
            filename = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_{date_str}.json')
            subset.to_json(filename, orient="records")
            print(f"Saved {len(subset)} records to {filename}")
        else:
            print(f"No records found for bucket '{bucket_name}'.")

    # Copy dated JSON files to latest
    for bucket_name in ["Options - Index", "Cash", "Stocks"]:
        dated_file = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_{date_str}.json')
        latest_file = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_latest.json')
        if os.path.exists(dated_file):
            shutil.copyfile(dated_file, latest_file)
            print(f"Copied {dated_file} to {latest_file}")

    # Generate available dates JSON
    generate_available_dates_json()

if __name__ == '__main__':
    main()
