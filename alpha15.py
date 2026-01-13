import pandas as pd
import numpy as np
import requests
import logging
from openalgo import api
from datetime import datetime, timedelta
import time
import pytz
import sys
import re
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"ALPHA15_{datetime.today().date()}.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def clean_stock_name(fut_symbol, expiry_day):
    """Extract base stock name from futures symbol."""
    return re.split(str(expiry_day), fut_symbol, maxsplit=1)[0]


def load_credentials(file_path="credentials.txt"):
    """Load credentials from file."""
    creds = {}
    with open(file_path, "r") as file:
        for line in file:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                creds[key] = value
    return creds


def load_symbols(file_path="symbols.txt"):
    """Load trading symbols from file."""
    with open(file_path, "r") as file:
        return [line.strip() for line in file if line.strip()]


# Load credentials
creds = load_credentials()
OPENALGO_API_KEY = creds["OPENALGO_API_KEY"]
OPENALGO_HOST = creds["OPENALGO_HOST"]
bot_token = creds["bot_token"]
chat_id = creds["chat_id"]

# Initialize OpenAlgo client
client = api(api_key=OPENALGO_API_KEY, host=OPENALGO_HOST)
logger.info(f"OpenAlgo client initialized with host: {OPENALGO_HOST}")

# Load symbols
symbols = load_symbols()
logger.info(f"Loaded {len(symbols)} symbols from symbols.txt")

# Time zone setup
TIME_ZONE = pytz.timezone('Asia/Kolkata')


def get_holidays():
    """Fetch market holidays from OpenAlgo."""
    try:
        holidays_response = client.holidays()
        if holidays_response.get('status') == 'success':
            # Extract holiday dates
            holidays_data = holidays_response.get('data', [])
            holiday_dates = [h.get('date') for h in holidays_data if h.get('date')]
            logger.info(f"Fetched {len(holiday_dates)} holidays from OpenAlgo")
            return holiday_dates
        else:
            logger.warning("Failed to fetch holidays, using empty list")
            return []
    except Exception as e:
        logger.error(f"Error fetching holidays: {e}")
        return []


def get_last_trading_day(current_date, holidays=None):
    """Returns the most recent trading day (Monday to Friday) before the given date."""
    if holidays is None:
        holidays = []
    
    last_day = current_date - timedelta(days=1)
    while last_day.weekday() >= 5 or last_day.strftime('%Y-%m-%d') in holidays:
        last_day -= timedelta(days=1)
    return last_day


def send_telegram_message(message):
    """Send alert via Telegram."""
    max_retries = 3
    for retry in range(max_retries):
        try:
            url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
            payload = {'chat_id': chat_id, 'text': message}
            response = requests.post(url, data=payload)
            logger.info(f"Telegram message sent: {message}")
            return response
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            if retry < max_retries - 1:
                logger.info("Retrying...")
                time.sleep(1)
            else:
                logger.error("Max retries exceeded for Telegram message.")


def calculate_atr(symbol, exchange="NFO"):
    """Calculate 14-period ATR using OpenAlgo history API."""
    ist = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist).date()
    from_date = today - timedelta(days=90)
    
    try:
        # OpenAlgo history API
        hist_response = client.history(
            symbol=symbol,
            exchange=exchange,
            interval="D",  # Daily interval
            start_date=from_date.strftime('%Y-%m-%d'),
            end_date=today.strftime('%Y-%m-%d')
        )
        
        if hist_response.get('status') == 'success' and hist_response.get('data'):
            df = pd.DataFrame(hist_response['data'])
            
            # Ensure proper column names
            df.columns = [c.lower() for c in df.columns]
            
            if len(df) < 15:
                logger.error(f"Not enough data for ATR calculation for {symbol}")
                return None
            
            df['H-L'] = df['high'] - df['low']
            df['H-PC'] = abs(df['high'] - df['close'].shift(1))
            df['L-PC'] = abs(df['low'] - df['close'].shift(1))
            df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
            
            # Calculate ATR using Wilder's smoothing
            atr = [df['TR'].iloc[:14].mean()]
            for i in range(14, len(df)):
                atr.append((atr[-1] * (14 - 1) + df['TR'].iloc[i]) / 14)
            df['ATR'] = pd.Series(atr, index=df.index[13:])
            
            atr_value = df['ATR'].iloc[-1]
            logger.info(f"ATR for {symbol}: {atr_value:.2f}")
            return atr_value
        else:
            logger.error(f"Failed to fetch history for ATR: {hist_response}")
            return None
            
    except Exception as e:
        logger.error(f"Error calculating ATR for {symbol}: {e}")
        return None


def calculate_poc(symbol, tick_size, exchange="NFO", holidays=None):
    """Calculate Point of Control using TPO Market Profile."""
    ist = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist).date()
    yesterday = get_last_trading_day(today, holidays)
    
    try:
        # Fetch 15-min candles from previous trading day
        hist_response = client.history(
            symbol=symbol,
            exchange=exchange,
            interval="15m",
            start_date=yesterday.strftime('%Y-%m-%d'),
            end_date=yesterday.strftime('%Y-%m-%d')
        )
        
        if hist_response.get('status') == 'success' and hist_response.get('data'):
            df = pd.DataFrame(hist_response['data'])
            df.columns = [c.lower() for c in df.columns]
            
            if df.empty:
                logger.error(f"No 15-min candle data for POC calculation for {symbol}")
                return None
            
            # Build TPO Market Profile
            tick_size_adj = tick_size * 0.05
            min_price = np.floor(df['low'].min() / tick_size_adj) * tick_size_adj
            max_price = np.ceil(df['high'].max() / tick_size_adj) * tick_size_adj
            price_bins = np.arange(min_price, max_price + tick_size_adj, tick_size_adj)
            
            import string
            letters = list(string.ascii_uppercase) + list(string.ascii_lowercase)
            market_profile = {price: "" for price in price_bins}
            tpo_count = {price: 0 for price in price_bins}
            
            for i, row in df.iterrows():
                letter = letters[i] if i < len(letters) else '?'
                for price in price_bins:
                    price_range_low = price
                    price_range_high = price + tick_size_adj
                    if row['low'] <= price_range_high and row['high'] >= price_range_low:
                        market_profile[price] += letter
                        tpo_count[price] += 1
            
            profile_df = pd.DataFrame(list(market_profile.items()), columns=['Price', 'TPO'])
            profile_df['TPO_count'] = profile_df['Price'].map(tpo_count)
            profile_df = profile_df[profile_df['TPO'] != ""]
            
            if profile_df.empty:
                logger.error(f"No valid TPO profile for {symbol}")
                return None
            
            poc = profile_df.loc[profile_df['TPO_count'].idxmax(), 'Price']
            logger.info(f"POC for {symbol}: {poc:.2f}")
            return poc
        else:
            logger.error(f"Failed to fetch history for POC: {hist_response}")
            return None
            
    except Exception as e:
        logger.error(f"Error calculating POC for {symbol}: {e}")
        return None


def get_15min_candles(symbol, exchange="NFO"):
    """Get today's 15-minute candles using OpenAlgo history API."""
    ist = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist).date()
    current_time = datetime.now(ist)
    
    if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 30):
        logger.warning(f"Skipping data fetch for {symbol}: First 15-min candle not yet complete")
        return None
    
    try:
        hist_response = client.history(
            symbol=symbol,
            exchange=exchange,
            interval="15m",
            start_date=today.strftime('%Y-%m-%d'),
            end_date=today.strftime('%Y-%m-%d')
        )
        
        if hist_response.get('status') == 'success' and hist_response.get('data'):
            candles = pd.DataFrame(hist_response['data'])
            candles.columns = [c.lower() for c in candles.columns]
            logger.info(f"15-min candles for {symbol}: {len(candles)} candles retrieved")
            return candles
        else:
            logger.error(f"No 15-min candle data for {symbol}: {hist_response}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching 15-min candles for {symbol}: {e}")
        return None


def get_ltp(symbol, exchange="NFO"):
    """Get current LTP using OpenAlgo quotes API."""
    try:
        quote_response = client.quotes(symbol=symbol, exchange=exchange)
        
        if quote_response.get('status') == 'success' and quote_response.get('data'):
            ltp = quote_response['data'].get('ltp')
            logger.info(f"LTP for {symbol}: {ltp}")
            return ltp
        else:
            logger.error(f"Failed to fetch LTP for {symbol}: {quote_response}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching LTP for {symbol}: {e}")
        return None


def check_trading_conditions(symbol, tick_size, expiry_day, exchange="NFO", holidays=None):
    """Check if trading conditions are met for the symbol."""
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    logger.info(f"Checking trading conditions for {symbol} at {current_time}")

    # Ensure we're in the monitoring window (9:30 AM - 9:45 AM)
    if not (current_time.hour == 9 and 30 <= current_time.minute <= 45):
        logger.info(f"Outside monitoring window for {symbol}")
        #return None

    # Get POC
    poc = calculate_poc(symbol, tick_size, exchange, holidays)
    if poc is None:
        logger.info(f"Skipping {symbol} due to missing POC")
        return None

    # Get first two 15-minute candles
    candles_15min = get_15min_candles(symbol, exchange)
    if candles_15min is None or len(candles_15min) < 2:
        logger.info(f"Skipping {symbol} due to missing first or second 15-min candle")
        return None

    # Get ATR
    atr = calculate_atr(symbol, exchange)
    if atr is None:
        logger.info(f"Skipping {symbol} due to missing ATR")
        return None

    # First candle details
    first_candle = candles_15min.iloc[0]
    fc_open = float(first_candle['open'])
    fc_low = float(first_candle['low'])
    fc_high = float(first_candle['high'])
    fc_close = float(first_candle['close'])
    logger.info(f"{symbol} - First candle: Open: {fc_open}, Low: {fc_low}, High: {fc_high}, Close: {fc_close}")

    # Get current LTP
    current_ltp = get_ltp(symbol, exchange)
    if current_ltp is None:
        logger.error(f"Failed to fetch LTP for {symbol}")
        return None

    open_to_high = fc_high - fc_open
    open_to_low = fc_open - fc_low
    signal = None

    if fc_open > poc:
        buy_conditions = [
            fc_open > poc,
            atr > open_to_high,
            current_ltp > fc_high  # Breakout above first candle high
        ]
        logger.info(f"{symbol} - Buy conditions: Open > POC: {fc_open > poc}, "
                    f"ATR > Range: {atr > open_to_high}, "
                    f"Breakout: {current_ltp > fc_high} (LTP: {current_ltp}, First High: {fc_high})")
        if all(buy_conditions):
            stock_name = clean_stock_name(symbol, expiry_day)
            message = f"🟢 BUY: {stock_name} at LTP: {current_ltp}"
            send_telegram_message(message)
            signal = "BUY"
        else:
            logger.info(f"No buy signal for {symbol}")
    elif fc_open < poc:
        sell_conditions = [
            fc_open < poc,
            atr > open_to_low,
            current_ltp < fc_low  # Breakout below first candle low
        ]
        logger.info(f"{symbol} - Sell conditions: Open < POC: {fc_open < poc}, "
                    f"ATR > Range: {atr > open_to_low}, "
                    f"Breakout: {current_ltp < fc_low} (LTP: {current_ltp}, First Low: {fc_low})")
        if all(sell_conditions):
            stock_name = clean_stock_name(symbol, expiry_day)
            message = f"🔴 SELL: {stock_name} at LTP: {current_ltp}"
            send_telegram_message(message)
            signal = "SELL"
        else:
            logger.info(f"No sell signal for {symbol}")
    else:
        logger.info(f"No signal for {symbol}: Open equals POC ({fc_open})")

    return signal


def signal_detection(expiry_day):
    """Main signal detection loop."""
    ist = pytz.timezone('Asia/Kolkata')
    
    # Fetch holidays from OpenAlgo
    holidays = get_holidays()
    
    # Create symbol data (using default tick_size since OpenAlgo handles this)
    # You can customize tick_size per symbol if needed
    symbol_data = [{"symbol": s, "tick_size": 0.05} for s in symbols]
    
    logger.info(f"Starting signal detection for {len(symbol_data)} symbols")
    
    alerted_symbols = set()
    current_date = datetime.now(ist).date()

    while True:
        current_time = datetime.now(ist)
        
        # Reset alerted symbols if it's a new day
        if current_time.date() > current_date:
            logger.info("New trading day detected. Resetting alerted symbols.")
            alerted_symbols.clear()
            current_date = current_time.date()
            holidays = get_holidays()  # Refresh holidays

        # Restrict to 9:30 AM - 9:45 AM
        if current_time.hour > 9 or (current_time.hour == 9 and current_time.minute > 45):
            logger.info("Monitoring window (9:30 AM - 9:45 AM) ended. Stopping signal detection.")
            break
        if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 30):
            logger.info(f"Waiting for 9:30 AM: {current_time}")
            time.sleep(60)
            continue

        logger.info(f"Checking signals at {current_time}")
        failed_symbols = []
        
        for item in symbol_data:
            symbol = item['symbol']
            tick_size = item['tick_size']
            
            if symbol in alerted_symbols:
                logger.info(f"Skipping {symbol}: Already alerted today")
                continue
            
            logger.info(f"Processing symbol: {symbol}")
            try:
                signal = check_trading_conditions(
                    symbol, tick_size, expiry_day, 
                    exchange="NFO", holidays=holidays
                )
                if signal:
                    alerted_symbols.add(symbol)
                time.sleep(2)  # Delay to avoid API rate limits
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                failed_symbols.append(item)
                time.sleep(2)

        # Retry failed symbols
        if failed_symbols:
            logger.info(f"Retrying {len(failed_symbols)} failed symbols")
            for item in failed_symbols:
                symbol = item['symbol']
                tick_size = item['tick_size']
                
                if symbol in alerted_symbols:
                    logger.info(f"Skipping retry for {symbol}: Already alerted today")
                    continue
                
                logger.info(f"Retrying symbol: {symbol}")
                try:
                    signal = check_trading_conditions(
                        symbol, tick_size, expiry_day,
                        exchange="NFO", holidays=holidays
                    )
                    if signal:
                        alerted_symbols.add(symbol)
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Error retrying {symbol}: {e}")
                    time.sleep(2)

        if len(alerted_symbols) == len(symbols):
            logger.info("All symbols processed. Stopping signal detection.")
            break

        time.sleep(5)  # Check every 5 seconds for responsiveness
    
    logger.info("Signal detection completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Alpha15 Strategy - OpenAlgo Edition')
    parser.add_argument('--expiry-day', type=int, required=True,
                        help='Expiry day of current month (e.g., 31 for 31JUL25)')
    args = parser.parse_args()
    
    try:
        logger.info(f"Starting Alpha15 with expiry day: {args.expiry_day}")
        signal_detection(args.expiry_day)
    except KeyboardInterrupt:
        logger.info("Script terminated by user (KeyboardInterrupt).")
        sys.exit(0)