import time
import json
import math
import requests
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os

load_dotenv()

# ENVIRONMENT VARIABLES
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

SYMBOL = "TRXUSDT"
INTERVAL_5M = 5
INTERVAL_1H = 60
TP_BUFFER = 0.0007  # 0.07%
RISK_PERCENT = 0.1  # 10%

DATA_FILE = "trade_data.json"

def fetch_ohlc(session, interval, limit):
    res = session.get_kline(
        category="linear",
        symbol=SYMBOL,
        interval=str(interval),
        limit=limit
    )
    return res["result"]["list"]

def to_heikin_ashi(ohlc):
    ha_candles = []
    for i, candle in enumerate(ohlc):
        t, o, h, l, c, *_ = map(float, candle[:5])
        if i == 0:
            ha_open = (o + c) / 2
        else:
            ha_open = (ha_candles[-1][1] + ha_candles[-1][4]) / 2
        ha_close = (o + h + l + c) / 4
        ha_high = max(h, ha_open, ha_close)
        ha_low = min(l, ha_open, ha_close)
        ha_candles.append([t, ha_open, ha_high, ha_low, ha_close])
    return ha_candles

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"trades": [], "last_sequence": {"buy": None, "sell": None}, "confirmed": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def get_balance(session):
    res = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
    return float(res["result"]["list"][0]["coin"][0]["availableToTrade"])

def detect_sequence(candles, type_):
    sequence = []
    for candle in reversed(candles[:-1]):
        is_green = candle[4] > candle[1]
        if (type_ == "buy" and is_green) or (type_ == "sell" and not is_green):
            break
        sequence.insert(0, candle)
    return sequence

def signal_trigger(data, candles):
    last = candles[-1]
    signal = None

    if last[4] > last[1]:  # green
        red_seq = detect_sequence(candles, "sell")
        if len(red_seq) >= 2:
            last_low = min(c[3] for c in red_seq)
            prev_low = data["last_sequence"]["buy"]
            if not prev_low or last_low > prev_low:
                signal = {"type": "buy", "entry": last[4], "sl": last_low}
                data["last_sequence"]["buy"] = last_low

    elif last[4] < last[1]:  # red
        green_seq = detect_sequence(candles, "buy")
        if len(green_seq) >= 2:
            last_high = max(c[2] for c in green_seq)
            prev_high = data["last_sequence"]["sell"]
            if not prev_high or last_high < prev_high:
                signal = {"type": "sell", "entry": last[4], "sl": last_high}
                data["last_sequence"]["sell"] = last_high

    return signal

def confirm_signal(signal, h1_candles):
    last_hour = h1_candles[-1]
    if signal["type"] == "buy" and last_hour[4] > last_hour[1]:
        return True
    if signal["type"] == "sell" and last_hour[4] < last_hour[1]:
        return True
    return False

def calc_tp(entry, sl, type_):
    risk = abs(entry - sl)
    tp = entry + risk + (entry * TP_BUFFER) if type_ == "buy" else entry - risk - (entry * TP_BUFFER)
    return round(tp, 5)

def place_order(signal, session):
    entry, sl = signal["entry"], signal["sl"]
    tp = calc_tp(entry, sl, signal["type"])

    balance_main = get_balance(main_session)
    balance_sub = get_balance(sub_session)
    total_balance = balance_main + balance_sub
    risk_amount = total_balance * RISK_PERCENT
    quantity = round(risk_amount / abs(entry - sl), 2)

    fallback_quantity = round((balance_main * 0.9 if signal["type"] == "sell" else balance_sub * 0.9) / abs(entry - sl), 2)
    if quantity * abs(entry - sl) > (balance_main if signal["type"] == "sell" else balance_sub):
        quantity = fallback_quantity

    side = "Buy" if signal["type"] == "buy" else "Sell"
    close_side = "Sell" if side == "Buy" else "Buy"
    account = sub_session if signal["type"] == "buy" else main_session

    print(f"Placing {side} trade: entry={entry}, SL={sl}, TP={tp}, qty={quantity}")

    # Main trade
    account.place_order(
        category="linear",
        symbol=SYMBOL,
        side=side,
        orderType="Market",
        qty=quantity,
        positionIdx=3
    )

    # TP
    account.place_order(
        category="linear",
        symbol=SYMBOL,
        side=close_side,
        orderType="Limit",
        qty=quantity,
        price=str(tp),
        timeInForce="GTC",
        reduceOnly=True,
        positionIdx=3
    )

    # SL
    account.place_order(
        category="linear",
        symbol=SYMBOL,
        side=close_side,
        orderType="Limit",
        qty=quantity,
        price=str(sl),
        timeInForce="GTC",
        reduceOnly=True,
        positionIdx=3
    )

    return {
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "type": signal["type"],
        "quantity": quantity,
        "status": "open",
        "timestamp": time.time()
    }

def rebalance():
    b1 = get_balance(main_session)
    b2 = get_balance(sub_session)
    total = b1 + b2
    if total == 0:
        return
    if total >= 2 * load_data().get("last_split", 0):
        split_amount = total / 2
        print("Splitting balance...")
        # You must implement fund transfer here based on your Bybit API sub-account/margin logic

def loop():
    while True:
        try:
            print(f"\nChecking @ {datetime.utcnow().strftime('%H:%M:%S')} UTC")

            data = load_data()

            ohlc_5m = fetch_ohlc(main_session, INTERVAL_5M, 100)
            ha_5m = to_heikin_ashi(ohlc_5m)

            ohlc_1h = fetch_ohlc(main_session, INTERVAL_1H, 3)
            ha_1h = to_heikin_ashi(ohlc_1h)

            now = datetime.utcnow()
            signal = signal_trigger(data, ha_5m)

            if signal:
                current_hour = now.replace(minute=0, second=0, microsecond=0).isoformat()
                if data["confirmed"].get("hour") != current_hour:
                    if confirm_signal(signal, ha_1h):
                        trade = place_order(signal, sub_session if signal["type"] == "buy" else main_session)
                        data["trades"].append(trade)
                        data["confirmed"]["hour"] = current_hour
                        save_data(data)
                        rebalance()
                    else:
                        print("Signal not confirmed")
                else:
                    print("Signal already used this hour")
            else:
                print("No valid signal")

        except Exception as e:
            print("Error:", e)

        time.sleep(300)  # 5-minute interval

if __name__ == "__main__":
    loop()
    
