from fastapi import FastAPI
from pybit.unified_trading import HTTP
import os
import uvicorn
from datetime import datetime, timedelta
import asyncio

app = FastAPI()

# === API KEYS ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")
NEW_SUB_UID = os.getenv("NEW_SUB_UID")

symbol = "TRXUSDT"

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

# === Global states ===
initial_balance = float(os.getenv("INITIAL_BALANCE", "754.35"))
baseline_balance = initial_balance

buy_seq_low = None
last_buy_seq_low = None
prev_buy_seq_low = None

sell_seq_high = None
last_sell_seq_high = None
prev_sell_seq_high = None

confirmed_buy_level = None
confirmed_sell_level = None

# === Balance helpers ===
def get_usdt_balance(session):
    data = session.get_wallet_balance(accountType="UNIFIED")
    coins = data["result"]["list"][0]["coin"]
    usdt = next((x for x in coins if x["coin"] == "USDT"), None)
    return float(usdt["equity"]) if usdt else 0

async def monitor_balance_and_transfer():
    global baseline_balance

    while True:
        try:
            main_bal = get_usdt_balance(main_session)
            sub_bal = get_usdt_balance(sub_session)
            combined = main_bal + sub_bal

            print(f"💰 Combined balance: {combined}, Baseline: {baseline_balance}")

            if combined >= baseline_balance * 2:
                amount_to_send = combined * 0.25
                print(f"🚀 Balance doubled! Sending {amount_to_send} to new sub account.")

                res = main_session.transfer_sub_account(
                    transferType=1,
                    coin="USDT",
                    amount=str(amount_to_send),
                    fromMemberId=0,
                    toMemberId=NEW_SUB_UID
                )
                print("✅ Transfer result:", res)

                # Update baseline after transfer
                baseline_balance = get_usdt_balance(main_session) + get_usdt_balance(sub_session)
                print(f"📊 New baseline set to: {baseline_balance}")

        except Exception as e:
            print("❌ Error in balance monitor:", e)

        await asyncio.sleep(60)

# === Candle utilities (get Heikin Ashi data) ===
def fetch_heikin_ashi(session, interval):
    raw = session.get_kline(category="linear", symbol=symbol, interval=interval, limit=3)["result"]["list"]
    candles = []
    for k in raw:
        open_p, high_p, low_p, close_p = map(float, k[1:5])
        # Heikin Ashi formula
        ha_close = (open_p + high_p + low_p + close_p) / 4
        if len(candles) == 0:
            ha_open = (open_p + close_p) / 2
        else:
            ha_open = (candles[-1]['ha_open'] + candles[-1]['ha_close']) / 2
        ha_high = max(high_p, ha_open, ha_close)
        ha_low = min(low_p, ha_open, ha_close)
        candles.append({
            "ha_open": ha_open,
            "ha_close": ha_close,
            "ha_high": ha_high,
            "ha_low": ha_low
        })
    return candles

async def check_signals():
    global buy_seq_low, last_buy_seq_low, prev_buy_seq_low
    global sell_seq_high, last_sell_seq_high, prev_sell_seq_high
    global confirmed_buy_level, confirmed_sell_level

    while True:
        try:
            candles_1h = fetch_heikin_ashi(main_session, "60")
            last_1h = candles_1h[-2]

            # Check for 1h buy level
            if last_1h["ha_close"] > last_1h["ha_open"]:
                if buy_seq_low is None:
                    buy_seq_low = last_1h["ha_low"]
                else:
                    buy_seq_low = min(buy_seq_low, last_1h["ha_low"])
            else:
                if buy_seq_low and last_1h["ha_low"] > buy_seq_low:
                    prev_buy_seq_low = last_buy_seq_low
                    last_buy_seq_low = buy_seq_low
                    if prev_buy_seq_low and last_buy_seq_low > prev_buy_seq_low:
                        confirmed_buy_level = last_1h["ha_open"]
                        print("✅ Confirmed 1h buy level:", confirmed_buy_level)
                    buy_seq_low = None

            # Check for 1h sell level
            if last_1h["ha_close"] < last_1h["ha_open"]:
                if sell_seq_high is None:
                    sell_seq_high = last_1h["ha_high"]
                else:
                    sell_seq_high = max(sell_seq_high, last_1h["ha_high"])
            else:
                if sell_seq_high and last_1h["ha_high"] < sell_seq_high:
                    prev_sell_seq_high = last_sell_seq_high
                    last_sell_seq_high = sell_seq_high
                    if prev_sell_seq_high and last_sell_seq_high < prev_sell_seq_high:
                        confirmed_sell_level = last_1h["ha_open"]
                        print("✅ Confirmed 1h sell level:", confirmed_sell_level)
                    sell_seq_high = None

            # Check 5m trigger
            candles_5m = fetch_heikin_ashi(main_session, "5")
            last_5m = candles_5m[-2]

            price = last_5m["ha_close"]

            if confirmed_buy_level and price > confirmed_buy_level:
                print("🚀 5m Buy trigger matched, entering trade")
                await execute_trade("buy", price)
                confirmed_buy_level = None

            if confirmed_sell_level and price < confirmed_sell_level:
                print("🚀 5m Sell trigger matched, entering trade")
                await execute_trade("sell", price)
                confirmed_sell_level = None

        except Exception as e:
            print("❌ Error checking signals:", e)

        await asyncio.sleep(300)

async def execute_trade(side, entry_price):
    try:
        session = sub_session if side == "buy" else main_session
        label = "Sub" if side == "buy" else "Main"

        total_balance = get_usdt_balance(main_session) + get_usdt_balance(sub_session)
        account_balance = get_usdt_balance(session)
        risk_amount = total_balance * 0.10
        fallback_balance = account_balance * 0.90
        qty_usdt = risk_amount if account_balance >= risk_amount else fallback_balance

        sl_diff = entry_price * 0.01
        qty_estimated = qty_usdt / sl_diff
        max_qty = ((account_balance * 75) / entry_price) * 0.9
        qty = max(1, round(min(qty_estimated, max_qty)))

        tp = entry_price + (0.01 * entry_price) + (0.0007 * entry_price) if side == "buy" else entry_price - (0.01 * entry_price) - (0.0007 * entry_price)
        sl = entry_price - (0.01 * entry_price) if side == "buy" else entry_price + (0.01 * entry_price)

        print(f"📢 Placing {side.upper()} order | Qty: {qty} | Entry: {entry_price} | TP: {tp} | SL: {sl}")

        order = session.place_order(
            category="linear",
            symbol=symbol,
            side="Buy" if side == "buy" else "Sell",
            order_type="Market",
            qty=str(qty),
            position_idx=0
        )
        print(f"✅ {label} market order:", order)

        for price_level in [tp, sl]:
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Sell" if side == "buy" else "Buy",
                order_type="Limit",
                price=str(price_level),
                qty=str(qty),
                reduce_only=True,
                time_in_force="GTC",
                close_on_trigger=True,
                position_idx=0
            )

        print(f"🎯 TP and 🛡️ SL placed for {side.upper()}")

    except Exception as e:
        print("❌ Error placing trade:", e)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_balance_and_transfer())
    asyncio.create_task(check_signals())

@app.get("/")
async def root():
    return {"status": "Bot is running ✅"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
    
