import os
import pandas as pd
import datetime
import json
import shutil

# Constants
DATA_FOLDER = "data/SPYI-Files"
CSV_URL = "https://tinyurl.com/SPYI-Link"   # Auto-download link

with open("config.json") as f:
    CONFIG = json.load(f)

OPENING_PRICE = CONFIG["SPX"]   # Current underlying index level


def get_current_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def parse_option_info(option_str):
    """Extract expiry, type, and strike from option tickers (e.g., NDX 251017C23925000)."""
    try:
        parts = option_str.strip().split()
        if len(parts) < 2:
            return None, None, None
        code = parts[1]
        expiry_date = datetime.datetime.strptime(code[:6], "%y%m%d").strftime("%Y-%m-%d")
        option_type = code[6]
        strike_price = int(code[7:]) / 1000
        return expiry_date, option_type, strike_price
    except Exception:
        return None, None, None


def assign_bucket_from_ticker(ticker):
    """Classify ticker into Options, Cash, or Stocks."""
    if isinstance(ticker, str):
        if ticker.startswith("SPX"):
            return "Options - Index"
        elif ticker.startswith("Cash"):
            return "Cash"
    return "Stocks"


def generate_available_dates_json():
    """Collect all saved dates and write available_dates.json."""
    date_set = set()
    for filename in os.listdir(DATA_FOLDER):
        if filename.startswith("SPYI_") and filename.endswith(".json") and "latest" not in filename:
            date_str = filename.split("_")[-1].replace(".json", "")
            date_set.add(date_str)
    dates = sorted(date_set)
    with open(os.path.join(DATA_FOLDER, "available_dates.json"), "w") as f:
        json.dump({"dates": dates}, f, indent=2)
    print(f"Generated available_dates.json with dates: {dates}")


def main():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    date_str = get_current_date()

    print(f"Downloading CSV for {date_str} ...")
    df = pd.read_csv(
        CSV_URL,
        usecols=['StockTicker', 'Price', 'MarketValue', 'Weightings', 'SecurityName']
    )
    df = df.dropna(subset=['StockTicker', 'Weightings'])

    # Clean numeric fields
    df['Price'] = pd.to_numeric(df['Price'].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
    df['MarketValue'] = pd.to_numeric(df['MarketValue'].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
    df['Weightings'] = pd.to_numeric(df['Weightings'].astype(str).str.replace('%', '').str.replace(',', ''), errors='coerce')
    df = df.dropna(subset=['Price', 'MarketValue'])

    # Assign buckets
    df['Bucket'] = df['StockTicker'].apply(assign_bucket_from_ticker)
    total_base_mv = df['MarketValue'].sum()

    for bucket_name in ["Options - Index", "Cash", "Stocks"]:
        subset = df[df['Bucket'] == bucket_name].copy()
        if subset.empty:
            print(f"No records found for bucket '{bucket_name}'.")
            continue

        if bucket_name == "Options - Index":
            # Parse option info
            subset[['Expiry_Date', 'Option_Type', 'Strike_Price']] = subset['StockTicker'].apply(
                lambda val: pd.Series(parse_option_info(val))
            )

            # Number of contracts (adjust for index option multiplier = 100)
            subset['Contracts'] = -subset['MarketValue'] / (subset['Price'] * 100)

            # Forgone gain if underlying > strike
            subset['ForgoneGain'] = ((OPENING_PRICE - subset['Strike_Price']) * 100 * subset['Contracts']).where(
                OPENING_PRICE > subset['Strike_Price'], 0
            )

            # Forgone gain as % of total base market value
            subset['ForgoneGainPct'] = subset['ForgoneGain'] / total_base_mv

            # Add Opening Price & Total Base MV for reference
            subset['OpeningPrice'] = OPENING_PRICE
            subset['TotalBaseMV'] = total_base_mv

            # Reorder columns
            subset = subset[['StockTicker', 'Weightings', 'Expiry_Date', 'Option_Type',
                             'Strike_Price', 'OpeningPrice', 'Contracts',
                             'ForgoneGain', 'ForgoneGainPct', 'TotalBaseMV']]

        else:
            subset = subset[['StockTicker', 'SecurityName', 'Weightings']]

        # Save dated JSON (keep values numeric — formatting done in frontend)
        filename = os.path.join(DATA_FOLDER, f'SPYI_{bucket_name.replace(" ", "_")}_{date_str}.json')
        subset.to_json(filename, orient="records", indent=2)
        print(f"Saved {len(subset)} records to {filename}")

        # Save "latest" JSON
        latest_file = os.path.join(DATA_FOLDER, f'SPYI_{bucket_name.replace(" ", "_")}_latest.json')
        shutil.copyfile(filename, latest_file)

    generate_available_dates_json()


if __name__ == '__main__':
    main()
