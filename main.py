from fastapi import FastAPI, Request
import asyncio
import os
from pybit.unified_trading import HTTP
from datetime import datetime

app = FastAPI()

# === Bybit sessions ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")
SUB_UID = os.getenv("SUB_UID")

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

# === Shared state ===
signals = {
    "buy": {"entry": None, "active": False},
    "sell": {"entry": None, "active": False},
}
high_low = {"high": None, "low": None}

# === Variables for 1-hour series logic ===
last_red_low, prev_red_low = None, None
last_green_high, prev_green_high = None, None
in_red_series, in_green_series = False, False

# === Get Heikin Ashi candle (Bybit linear) ===
def get_heikin_ashi_candle(timeframe="60"):
    data = main_session.get_kline(
        category="linear", symbol="TRXUSDT", interval=timeframe, limit=2
    )["result"]["list"]

    k = data[-2]
    open_, high, low, close = map(float, k[1:5])

    ha_close = (open_ + high + low + close) / 4
    ha_open = (open_ + close) / 2
    ha_high = max(high, ha_open, ha_close)
    ha_low = min(low, ha_open, ha_close)

    return ha_open, ha_high, ha_low, ha_close

# === Get 5-min high/low candle ===
def get_5m_high_low():
    data = main_session.get_kline(
        category="linear", symbol="TRXUSDT", interval="5", limit=2
    )["result"]["list"]

    k = data[-2]
    high = float(k[3])
    low = float(k[4])
    return high, low

def rebalance_funds():
    try:
        main = get_usdt_balance(main_session)
        sub = get_usdt_balance(sub_session)
        total = main + sub
        target = total / 2
        if abs(main - sub) < 0.1:
            print("✅ Balance already even.")
            return
        amount = abs(main - target)
        transfer_type = "MAIN_SUB" if main > target else "SUB_MAIN"
        main_session.create_internal_transfer(
            transfer_type=transfer_type,
            coin="USDT",
            amount=str(round(amount, 2)),
            sub_member_id=SUB_UID
        )
        print("🔁 Rebalanced main/sub")
    except Exception as e:
        print("❌ Rebalance failed:", e)

def get_usdt_balance(session):
    try:
        data = session.get_wallet_balance(accountType="UNIFIED")
        coins = data["result"]["list"][0]["coin"]
        usdt = next((x for x in coins if x["coin"] == "USDT"), None)
        return float(usdt["equity"]) if usdt else 0
    except:
        return 0

def cancel_all_orders(session):
    try:
        session.cancel_all_orders(category="linear", symbol="TRXUSDT")
        print("❌ All open orders cancelled for TRXUSDT")
    except Exception as e:
        print("⚠️ Failed to cancel orders:", e)

def close_positions(session, label):
    try:
        pos = session.get_positions(category="linear", symbol="TRXUSDT")["result"]["list"]
        for p in pos:
            size = float(p["size"])
            side = p["side"]
            if size > 0:
                close_side = "Sell" if side == "Buy" else "Buy"
                session.place_order(
                    category="linear",
                    symbol="TRXUSDT",
                    side=close_side,
                    order_type="Market",
                    qty=size,
                    reduce_only=True,
                    position_idx=0
                )
                print(f"✅ {label}: Closed {side} position with {size} contracts")
    except Exception as e:
        print(f"❌ {label} close failed:", e)

def get_current_price():
    data = main_session.get_tickers(category="linear", symbol="TRXUSDT")
    price = float(data["result"]["list"][0]["lastPrice"])
    return price

async def monitor(signal_type):
    session = sub_session if signal_type == "buy" else main_session
    label = "Sub" if signal_type == "buy" else "Main"

    entry = signals[signal_type]["entry"]
    high = high_low["high"]
    low = high_low["low"]

    if not entry or not high or not low:
        print(f"⚠️ Missing entry or high/low for {signal_type.upper()}")
        return

    sl = low if signal_type == "buy" else high
    rr = abs(entry - sl)
    extra = entry * 0.007
    tp = entry + 1.5 * rr + extra if signal_type == "buy" else entry - 1.5 * rr - extra

    balance = get_usdt_balance(session)
    total = get_usdt_balance(main_session) + get_usdt_balance(sub_session)
    risk = total * 0.10
    sl_diff = abs(entry - sl)
    leverage = 75
    qty_risk = risk / sl_diff
    max_qty = ((balance * leverage) / entry) * 0.9
    qty = max(1, round(min(qty_risk, max_qty)))

    print(f"👀 Monitoring for {signal_type.upper()} entry at {entry}...")

    while True:
        await asyncio.sleep(5)
        price = get_current_price()

        now = datetime.utcnow()
        if now.second == 0 and now.minute % 1 == 0:
            print(f"📊 Current price: {price}")

        if (signal_type == "buy" and price >= entry) or (signal_type == "sell" and price <= entry):
            print(f"🚀 Entry price hit for {signal_type.upper()} at {price}")

            cancel_all_orders(session)
            close_positions(session, label)

            session.place_order(
                category="linear",
                symbol="TRXUSDT",
                side="Buy" if signal_type == "buy" else "Sell",
                order_type="Market",
                qty=qty,
                reduce_only=False,
                position_idx=0
            )

            while True:
                await asyncio.sleep(5)
                current = get_current_price()
                if (signal_type == "buy" and (current >= tp or current <= sl)) or \
                   (signal_type == "sell" and (current <= tp or current >= sl)):
                    print(f"🎯 TP or SL hit for {signal_type.upper()} at {current}")
                    close_positions(session, label)
                    rebalance_funds()
                    break

            signals[signal_type]["entry"] = None
            signals[signal_type]["active"] = False
            print(f"✅ Trade closed for {signal_type.upper()}, ready for new signals.")
            break

async def periodic_tasks():
    global last_red_low, prev_red_low, last_green_high, prev_green_high
    global in_red_series, in_green_series

    while True:
        now = datetime.utcnow()

        if now.minute == 0 and now.second < 10:
            ha_open, ha_high, ha_low, ha_close = get_heikin_ashi_candle("60")
            is_green = ha_close > ha_open
            is_red = ha_close < ha_open

            if is_red:
                if not in_red_series:
                    prev_red_low = last_red_low
                    last_red_low = ha_low
                    in_red_series = True
                    in_green_series = False
                else:
                    last_red_low = min(last_red_low, ha_low)

            if is_green:
                if not in_green_series:
                    prev_green_high = last_green_high
                    last_green_high = ha_high
                    in_green_series = True
                    in_red_series = False
                else:
                    last_green_high = max(last_green_high, ha_high)

            buy_condition = is_red and in_red_series and prev_red_low is not None and last_red_low > prev_red_low
            sell_condition = is_green and in_green_series and prev_green_high is not None and last_green_high < prev_green_high

            if buy_condition and not signals["buy"]["active"]:
                signals["buy"]["entry"] = (ha_close + ha_open) / 2
                signals["buy"]["active"] = True
                asyncio.create_task(monitor("buy"))
                print(f"✅ New BUY signal stored at {signals['buy']['entry']}")

            if sell_condition and not signals["sell"]["active"]:
                signals["sell"]["entry"] = (ha_close + ha_open) / 2
                signals["sell"]["active"] = True
                asyncio.create_task(monitor("sell"))
                print(f"✅ New SELL signal stored at {signals['sell']['entry']}")

        if now.minute % 5 == 0 and now.second < 10:
            high, low = get_5m_high_low()
            high_low["high"] = high
            high_low["low"] = low
            print(f"📊 Updated 5-min high/low: High={high}, Low={low}")

        await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_tasks())

@app.on_event("startup")
async def heartbeat():
    async def print_heartbeat():
        while True:
            await asyncio.sleep(300)
            print("✅ Bot is running")
    asyncio.create_task(print_heartbeat())

@app.post("/webhook")
async def webhook(request: Request):
    body = (await request.body()).decode().strip().lower()
    if body == "ok":
        print("that is okay")
        return {"message": "Received and logged"}
    else:
        return {"message": "Ignored"}

@app.get("/")
def health():
    return {"status": "Bot is online ✅"}
    
