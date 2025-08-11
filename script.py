import os
import requests
import datetime
import pandas as pd

DATA_FOLDER = "data"
URL = 'https://tinyurl.com/Pr0d1g10s0'

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
        # Format: day, month, year
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
            subset = subset[['Ticker', 'Weight', 'Expiry_Date', 'Option_Type', 'Strike_Price']]
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

            import shutil

# After saving each dated JSON file, also copy to "latest" filename
for bucket_name in ["Options - Index", "Cash", "Stocks"]:
    dated_file = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_{date_str}.json')
    latest_file = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_latest.json')
    if os.path.exists(dated_file):
        shutil.copyfile(dated_file, latest_file)

if __name__ == '__main__':
    main()
