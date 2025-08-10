import os
import requests
import datetime
import pandas as pd

# Folder inside repo (or your local test folder)
DATA_FOLDER = "data"
URL = 'https://tinyurl.com/Pr0d1g10s0'

def get_current_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def download_file(url, filename):
    response = requests.get(url)
    response.raise_for_status()
    with open(filename, 'wb') as file:
        file.write(response.content)

def main():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    date_str = get_current_date()

    # File names
    excel_filename = os.path.join(DATA_FOLDER, f'JEPQ_{date_str}.xlsx')
    json_filename = os.path.join(DATA_FOLDER, f'JEPQ_{date_str}.json')

    # Step 1 — Download Excel
    download_file(URL, excel_filename)

    # Step 2 — Read starting from Row 8 (header=7 because it's zero-based)
    df = pd.read_excel(excel_filename, header=7, usecols="C,F")

    # Step 3 — Drop empty rows
    df = df.dropna(subset=["Ticker", "Weight"])

    # Step 4 — Convert to JSON
    df.to_json(json_filename, orient="records")

    print(f"Saved cleaned data to {json_filename}")

if __name__ == '__main__':
    main()
