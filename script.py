import os
import requests
import datetime
import pandas as pd
import shutil

# Config
DATA_FOLDER = "data"
URL = 'https://tinyurl.com/Pr0d1g10s0'  # JEPQ Excel file

def get_current_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def download_file(url, filename):
    print(f"Downloading Excel from {url}")
    r = requests.get(url)
    r.raise_for_status()
    with open(filename, 'wb') as file:
        file.write(r.content)
    print(f"Saved Excel to {filename}")

def parse_option_info(option_str):
    try:
        option_str = option_str.strip()
        parts = option_str.split()
        if len(parts) < 2:
            return None, None, None

        code = parts[1]
        date_code = code[:6]  # YYMMDD
        expiry_date = datetime.datetime.strptime(date_code, "%y%m%d").strftime("%d %m %Y")
        option_type = code[6]
        strike_raw = code[7:]
        strike_price = f"{int(strike_raw) / 1000:,.2f}"

        return expiry_date, option_type, strike_price
    except Exception:
        return None, None, None

def main():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    date_str = get_current_date()

    excel_filename = os.path.join(DATA_FOLDER, f'JEPQ_{date_str}.xlsx')

    if not os.path.exists(excel_filename):
        download_file(URL, excel_filename)
    else:
        print("File already downloaded today.")

    # Read columns A, B, C, F from Excel (skip first 8 rows)
    df = pd.read_excel(excel_filename, header=None, usecols="A,B,C,F", skiprows=8)
    df.columns = ['Ticker_A', 'Ticker_B', 'Type', 'Weight']
    df = df.dropna(subset=['Type', 'Weight'])

    # Bucket assignment
    def assign_bucket(row):
        if row['Type'] == "Option - Index":
            return "Options - Index"
        elif row['Type'] == "Cash":
            return "Cash"
        else:
            return "Stocks"

    df['Bucket'] = df.apply(assign_bucket, axis=1)

    # Process & save each bucket
    for bucket_name in ["Options - Index", "Cash", "Stocks"]:
        subset = df[df['Bucket'] == bucket_name].copy()

        if bucket_name == "Options - Index":
            subset['Ticker'] = subset['Ticker_B']
            subset[['Expiry_Date', 'Option_Type', 'Strike_Price']] = subset['Ticker_B'].apply(
                lambda val: pd.Series(parse_option_info(val))
            )
            subset['Weight'] = (subset['Weight'] * 100).map(lambda x: f"{x:.2f}")
            subset = subset[['Ticker', 'Weight', 'Expiry_Date', 'Option_Type', 'Strike_Price']]
        else:
            subset['Ticker'] = subset['Ticker_A']
            subset['Weight'] = (subset['Weight'] * 100).map(lambda x: f"{x:.2f}")
            subset = subset[['Ticker', 'Weight']]

        if not subset.empty:
            dated_file = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_{date_str}.json')
            latest_file = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_latest.json')

            subset.to_json(dated_file, orient="records")
            shutil.copyfile(dated_file, latest_file)

            print(f"Saved {len(subset)} records to {dated_file} and {latest_file}")
        else:
            print(f"No records found for bucket '{bucket_name}'.")

if __name__ == '__main__':
    main()
