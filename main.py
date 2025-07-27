import requests
import time
import hmac
import hashlib
import json
from datetime import datetime
from typing import List, Dict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# === USER CONFIGURATION ===
MAIN_API_KEY = "YOUR_MAIN_API_KEY"
MAIN_API_SECRET = "YOUR_MAIN_API_SECRET"
SUB_API_KEY = "YOUR_SUB_API_KEY"
SUB_API_SECRET = "YOUR_SUB_API_SECRET"
SPARE_SUB_ACCOUNT_ID = "spare_sub_id"  # Optional

BASE_URL = "https://api.bybit.com"
SYMBOL = "TRXUSDT"
RISK_PERCENT = 0.10
LEVERAGE = 75
CONFIRMATION_EXPIRY = 60 * 60  # 1 hour
RR = 1
RR_BUFFER = 0.0007  # 0.07%

# === GLOBAL STATE ===
candles: List[Dict] = []
last_buy_level = 0
last_sell_level = 999999
pending_signal = None
trade_history = []

# === FASTAPI APP ===
app = FastAPI()

@app.get("/")
def read_root():
    return JSONResponse(content={"message": "Bybit bot is running."})


# === AUTH HELPERS ===
def headers(api_key):
    return {
        "Content-Type": "application/json",
        "X-BYBIT-API-KEY": api_key
    }


# === CANDLE + STRATEGY ===
def fetch_candles(interval="5"):
    url = f"{BASE_URL}/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": SYMBOL,
        "interval": interval,
        "limit": 200
    }
    response = requests.get(url, params=params)
    data = response.json()["result"]["list"]
    return list(reversed([{
        "timestamp": int(c[0]),
        "open": float(c[1]),
        "high": float(c[2]),
        "low": float(c[3]),
        "close": float(c[4])
    } for c in data]))


def to_heikin_ashi(candles: List[Dict]) -> List[Dict]:
    ha = []
    for i, c in enumerate(candles):
        close = (c["open"] + c["high"] + c["low"] + c["close"]) / 4
        open_ = (c["open"] + c["close"]) / 2 if i == 0 else (ha[i - 1]["open"] + ha[i - 1]["close"]) / 2
        high = max(c["high"], open_, close)
        low = min(c["low"], open_, close)
        ha.append({
            "timestamp": c["timestamp"],
            "open": open_,
            "high": high,
            "low": low,
            "close": close
        })
    return ha


def check_buy_sell_signal(ha_candles):
    global last_buy_level, last_sell_level
    i = len(ha_candles) - 1
    cur = ha_candles[i]
    prevs = ha_candles[:i]

    def get_sequence(candles, color):
        seq = []
        for c in reversed(candles):
            if (c["close"] > c["open"]) == color:
                seq.insert(0, c)
            else:
                break
        return seq

    red_seq = get_sequence(prevs, False)
    green_seq = get_sequence(prevs, True)

    if cur["close"] > cur["open"]:
        low = min(c["low"] for c in red_seq)
        if low > last_buy_level:
            last_buy_level = low
            return {"type": "buy", "entry": cur["close"], "sl": low}
    elif cur["close"] < cur["open"]:
        high = max(c["high"] for c in green_seq)
        if high < last_sell_level:
            last_sell_level = high
            return {"type": "sell", "entry": cur["close"], "sl": high}
    return None


# === TRADING & BALANCE ===
def get_account_balance(api_key, api_secret):
    url = f"{BASE_URL}/v5/account/wallet-balance?accountType=UNIFIED"
    response = requests.get(url, headers=headers(api_key))
    return float(response.json()["result"]["list"][0]["totalEquity"])


def calculate_tp(entry, sl, direction):
    risk = abs(entry - sl)
    tp = entry + (risk * RR) if direction == "buy" else entry - (risk * RR)
    buffer = entry * RR_BUFFER
    return tp + buffer if direction == "buy" else tp - buffer


def execute_trade(signal):
    key, secret = (SUB_API_KEY, SUB_API_SECRET) if signal["type"] == "buy" else (MAIN_API_KEY, MAIN_API_SECRET)
    bal_main = get_account_balance(MAIN_API_KEY, MAIN_API_SECRET)
    bal_sub = get_account_balance(SUB_API_KEY, SUB_API_SECRET)
    total = bal_main + bal_sub
    qty_fund = total * RISK_PERCENT

    entry, sl = signal["entry"], signal["sl"]
    risk = abs(entry - sl)
    qty = round(qty_fund / risk * LEVERAGE, 1)
    tp = calculate_tp(entry, sl, signal["type"])

    print(f"[{signal['type'].upper()}] Entry: {entry}, SL: {sl}, TP: {tp}, Qty: {qty}")
    # You should place a real market order here with Bybit's authenticated endpoint

    trade_history.append({
        "type": signal["type"],
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "qty": qty,
        "status": "open",
        "timestamp": datetime.utcnow().isoformat()
    })


def rebalance_funds():
    print("Rebalancing funds between main and sub...")


def split_balance_if_doubled():
    print("Checking if balance doubled for split...")


# === MAIN LOOP ===
def run_once():
    global pending_signal
    raw_candles = fetch_candles("5")
    ha_candles = to_heikin_ashi(raw_candles)
    signal = check_buy_sell_signal(ha_candles)

    if signal:
        print(f"Signal detected: {signal}")
        execute_trade(signal)
        rebalance_funds()
        split_balance_if_doubled()


# Optional webhook to trigger run_once remotely
@app.post("/trigger")
async def trigger_signal(request: Request):
    run_once()
    return JSONResponse(content={"status": "signal triggered"})

if __name__ == "__main__":
    run_once()
    
