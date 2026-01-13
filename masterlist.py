"""
Masterlist Generator for Alpha15 Strategy (OpenAlgo Edition)
Downloads and filters F&O instruments using OpenAlgo API.
"""

import argparse
import sys
import io
from openalgo import api

# Fix Windows console encoding for Unicode
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Load credentials
def load_credentials(file_path="credentials.txt"):
    creds = {}
    with open(file_path, "r") as file:
        for line in file:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                creds[key] = value
    return creds

creds = load_credentials()
client = api(api_key=creds["OPENALGO_API_KEY"], host=creds["OPENALGO_HOST"])

# Valid stock names to track
VALID_NAMES = [
    "ACC", "ANGELONE", "ASIANPAINT", "ASTRAL", "AUROPHARMA", "DMART", "AXISBANK", "BSE",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BHARATFORG", "BHARTIARTL", "BRITANNIA",
    "CDSL", "CHOLAFIN", "CIPLA", "COALINDIA", "COFORGE", "COLPAL", "CAMS", "COROMANDEL",
    "CUMMINSIND", "CYIENT", "DLF", "DABUR", "DALBHARAT", "DEEPAKNTR", "DIVISLAB", "DIXON",
    "LALPATHLAB", "DRREDDY", "EICHERMOT", "ESCORTS", "GODREJCP", "GODREJPROP", "GRASIM",
    "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HAVELLS", "HEROMOTOCO", "HINDALCO",
    "HAL", "HINDUNILVR", "ICICIBANK", "ICICIGI", "ICICIPRULI", "IRCTC", "INDUSINDBK",
    "NAUKRI", "INFY", "INDIGO", "JKCEMENT", "JSWSTEEL", "JSL", "JINDALSTEL", "JUBLFOOD",
    "KOTAKBANK", "LTF", "LTTS", "LTIM", "LT", "LUPIN", "MGL", "M&M", "MFSL", "METROPOLIS",
    "MPHASIS", "MCX", "MUTHOOTFIN", "NESTLEIND", "OBEROIRLTY", "PVRINOX", "PERSISTENT",
    "POLYCAB", "RELIANCE", "SBICARD", "SBILIFE", "SRF", "SHRIRAMFIN", "SBIN", "SUNPHARMA",
    "TATACONSUM", "TVSMOTOR", "TATACHEM", "TCS", "TATAMOTORS", "TECHM", "INDHOTEL",
    "TITAN", "TORNTPHARM", "TORNTPOWER", "TRENT", "TIINDIA", "UBL", "UNITDSPR", "VOLTAS",
    "ZYDUSLIFE"
]


def get_futures_symbols(expiry_month: str):
    """
    Fetch futures symbols from OpenAlgo and filter by valid names.

    Args:
        expiry_month: 3-letter month code (e.g., 'JUL', 'AUG')
    """
    print(f"[INFO] Fetching futures for expiry month: {expiry_month}")

    futures_list = []

    for stock in VALID_NAMES:
        try:
            # Search for the stock's futures
            result = client.search(query=stock, exchange="NFO")

            if result.get('status') == 'success' and result.get('data'):
                for instrument in result['data']:
                    symbol = instrument.get('symbol', '')
                    # Filter: must be a FUT contract for the specified month
                    if 'FUT' in symbol and expiry_month.upper() in symbol.upper():
                        futures_list.append({
                            'symbol': symbol,
                            'name': stock,
                            'token': instrument.get('token', ''),
                            'lotsize': instrument.get('lotsize', 1),
                            'tick_size': instrument.get('tick_size', 0.05)
                        })
                        print(f"  [OK] Found: {symbol}")
                        break  # Take first matching FUT for this stock
        except Exception as e:
            print(f"  [ERROR] Error searching {stock}: {e}")

    return futures_list


def save_symbols(futures_list, output_file="symbols.txt"):
    """Save futures symbols to symbols.txt"""
    with open(output_file, "w") as f:
        for fut in futures_list:
            f.write(fut['symbol'] + "\n")
    print(f"\n[SUCCESS] Saved {len(futures_list)} symbols to '{output_file}'")


def main():
    parser = argparse.ArgumentParser(description='Generate futures masterlist using OpenAlgo')
    parser.add_argument('--month', type=str, required=True,
                        help='3-letter expiry month (e.g., JAN, FEB, MAR, JUL)')
    parser.add_argument('--output', type=str, default='symbols.txt',
                        help='Output file for symbols (default: symbols.txt)')
    args = parser.parse_args()

    # Fetch and filter futures
    futures = get_futures_symbols(args.month)

    if futures:
        save_symbols(futures, args.output)
        print(f"\n[DONE] Generated symbols for {len(futures)} stocks")
    else:
        print("\n[ERROR] No futures found. Check your OpenAlgo connection or month format.")


if __name__ == "__main__":
    main()
