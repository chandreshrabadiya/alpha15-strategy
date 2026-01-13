# 🔺 Alpha15 Strategy

**Alpha15** is a real-time options signal engine for the Indian stock market based on futures data and intraday price action.

This system monitors the **second 15-minute candle** of the trading day to detect directional breakout signals on selected futures contracts. When a valid signal is detected, the bot sends **ATM option trade alerts** to a Telegram channel (Buy → ATM CE, Sell → ATM PE).

---

## ⚙️ Features

- ✅ Works with **OpenAlgo** (Broker Agnostic)
- ✅ Analyzes real-time **15-minute candles**
- ✅ Applies **ATR** and **POC (Point of Control)** logic
- ✅ Implements **TPO (Time-Price-Opportunity)** market profiling concepts
- ✅ Sends actionable alerts via **Telegram**
- ✅ Automated symbol fetching via `masterlist.py`
- ✅ External config via `credentials.txt` (gitignored)

---

## 🧠 Strategy Logic

This bot internally uses:
- Volume-based **POC** identification using TPO Market Profiling
- Volatility filters using **ATR (Average True Range)**
- Real-time breakout confirmation against the first 15-minute candle range

These concepts are inspired by institutional market profiling and price action frameworks.

---

## 🛠️ Setup Instructions

### 1. Environment Setup

It is recommended to use a virtual environment to keep dependencies isolated.

**Windows (PowerShell):**
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Prepare `credentials.txt`

Create a file named `credentials.txt` in the root folder (or use `credentials.template.txt` as a base) and fill in your details:

```text
OPENALGO_API_KEY=your_openalgo_api_key
OPENALGO_HOST=your_openalgo_host_url
bot_token=your_telegram_bot_token
chat_id=your_telegram_chat_id
```

### 3. Fetch Symbols (`masterlist.py`)

Run the masterlist script to generate the `symbols.txt` file for the current expiry month.

```powershell
# Generate symbols for January expiry
python masterlist.py --month JAN
```

### 4. Run the Bot (`alpha15.py`)

Run the bot during market hours. Ensure you specify the correct expiry day.

```powershell
# Run the bot for expiry day 27
python alpha15.py --expiry-day 27

# Run in test mode (bypasses time restrictions)
python alpha15.py --expiry-day 27 --test-mode
```

---

## 📢 Disclaimer

This tool is built for educational and experimental purposes only.  
It is **not financial advice**. Use at your own risk.

---

© 2025 – Alpha15
