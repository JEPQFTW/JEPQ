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
        strike_price = f"{int(strike_raw) / 1000:,.2f}"
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

    # Read columns A, B, C, F
    df = pd.read_excel(excel_filename, header=None, usecols="A,B,C,F", skiprows=8)
    df.columns = ['Ticker_A', 'Ticker_B', 'Type', 'Weight']
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

    # Save JSON files by bucket with tailored columns
    for bucket_name in ["Options - Index", "Cash", "Stocks"]:
        subset = df[df['Bucket'] == bucket_name].copy()

        if bucket_name == "Options - Index":
            subset['Ticker'] = subset['Ticker_B']
            subset[['Expiry_Date', 'Option_Type', 'Strike_Price']] = subset['Ticker_B'].apply(
                lambda val: pd.Series(parse_option_info(val))
            )
            subset['Weight'] = (subset['Weight'] * 100).map(lambda x: f"{x:.2f}")
            subset['OpeningPrice'] = 23384  # hardcoded underlying price
            subset = subset[['Ticker', 'Weight', 'Expiry_Date', 'Option_Type', 'Strike_Price', 'OpeningPrice']]
        else:
            subset['Ticker'] = subset['Ticker_A']
            subset['Weight'] = (subset['Weight'] * 100).map(lambda x: f"{x:.2f}")
            subset = subset[['Ticker', 'Weight']]

        if not subset.empty:
            filename = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_{date_str}.json')
            subset.to_json(filename, orient="records")
            print(f"Saved {len(subset)} records to {filename}")
        else:
            print(f"No records found for bucket '{bucket_name}'.")

    # Copy dated JSON files to "latest" versions
    for bucket_name in ["Options - Index", "Cash", "Stocks"]:
        dated_file = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_{date_str}.json')
        latest_file = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_latest.json')
        if os.path.exists(dated_file):
            shutil.copyfile(dated_file, latest_file)
            print(f"Copied {dated_file} to {latest_file}")

    # Generate the available_dates.json file
    generate_available_dates_json()

if __name__ == '__main__':
    main()
