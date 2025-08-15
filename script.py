import os
import requests
import datetime
import pandas as pd
import shutil

DATA_FOLDER = "data"
EXCEL_URL = 'https://tinyurl.com/Pr0d1g10s0'

def get_current_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def download_file(url, filename):
    response = requests.get(url)
    response.raise_for_status()
    with open(filename, 'wb') as file:
        file.write(response.content)

def generate_available_dates_json():
    dates = sorted({
        f.split('_')[-1].replace('.json', '')
        for f in os.listdir(DATA_FOLDER)
        if f.endswith(".json") and "_latest" not in f
    })
    output_path = os.path.join(DATA_FOLDER, "available_dates.json")
    with open(output_path, "w") as f:
        f.write(pd.Series(dates).to_json(orient="values"))
    print("Updated available_dates.json")

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

def fetch_live_price():
    try:
        r = requests.get(UNDERLYING_API_URL)
        r.raise_for_status()
        data = r.json()
        return data['quoteResponse']['result'][0]['regularMarketPrice']
    except Exception as e:
        print(f"Error fetching live price: {e}")
        return None


def main():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    date_str = get_current_date()
    excel_filename = os.path.join(DATA_FOLDER, f'JEPQ_{date_str}.xlsx')

    # Download Excel if not already downloaded
    if not os.path.exists(excel_filename):
        download_file(EXCEL_URL, excel_filename)
    else:
        print("Excel file already exists for today.")

    # Read Excel (columns A, B, C, F starting from row 9)
    df = pd.read_excel(excel_filename, header=None, usecols="A,B,C,F", skiprows=8)
    df.columns = ['Ticker_A', 'Ticker_B', 'Type', 'Weight']
    df = df.dropna(subset=['Type', 'Weight'])

    # Assign bucket
    df['Bucket'] = df['Type'].apply(lambda t: 
        "Options - Index" if t == "Option - Index" else
        ("Cash" if t == "Cash" else "Stocks")
    )

    # Fetch live price once
    live_price = fetch_live_price()
    print(f"Live QQQ Price: {live_price}")

    for bucket_name in ["Options - Index", "Cash", "Stocks"]:
        subset = df[df['Bucket'] == bucket_name].copy()

        dated_file = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_{date_str}.json')
        latest_file = os.path.join(DATA_FOLDER, f'JEPQ_{bucket_name.replace(" ", "_")}_latest.json')

        if bucket_name == "Options - Index":
            subset['Ticker'] = subset['Ticker_B']
            subset[['Expiry_Date', 'Option_Type', 'Strike_Price']] = subset['Ticker_B'].apply(
                lambda val: pd.Series(parse_option_info(val))
            )
            subset['Weight'] = (subset['Weight'] * 100).map(lambda x: f"{x:.2f}")

            # latest.json always gets live price
            subset_latest = subset.copy()
            subset_latest['UnderlyingPrice'] = live_price
            subset_latest[['Ticker', 'Weight', 'Expiry_Date', 'Option_Type', 'Strike_Price', 'UnderlyingPrice']].to_json(
                latest_file, orient="records"
            )

            # dated.json gets live price once and never overwrites
            if not os.path.exists(dated_file):
                subset_dated = subset.copy()
                subset_dated['UnderlyingPrice'] = live_price
                subset_dated[['Ticker', 'Weight', 'Expiry_Date', 'Option_Type', 'Strike_Price', 'UnderlyingPrice']].to_json(
                    dated_file, orient="records"
                )
                print(f"Saved new dated file for '{bucket_name}'")
            else:
                print(f"Dated file already exists for '{bucket_name}', skipping overwrite.")

        else:
            subset['Ticker'] = subset['Ticker_A']
            subset['Weight'] = (subset['Weight'] * 100).map(lambda x: f"{x:.2f}")

            # latest.json
            subset[['Ticker', 'Weight']].to_json(latest_file, orient="records")

            # dated.json
            if not os.path.exists(dated_file):
                subset[['Ticker', 'Weight']].to_json(dated_file, orient="records")
                print(f"Saved new dated file for '{bucket_name}'")
            else:
                print(f"Dated file already exists for '{bucket_name}', skipping overwrite.")

    generate_available_dates_json()


if __name__ == '__main__':
    main()
