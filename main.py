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

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

symbol = "TRXUSDT"

buy_window_until = None
sell_window_until = None

confirmed_buy_level = None
confirmed_sell_level = None

# === Helper functions ===
def get_heikin_ashi(candles):
    ha_open = (candles[0]["open"] + candles[0]["close"]) / 2
    ha_candles = []
    for c in candles:
        ha_close = (c["open"] + c["high"] + c["low"] + c["close"]) / 4
        ha_high = max(c["high"], ha_open, ha_close)
        ha_low = min(c["low"], ha_open, ha_close)
        ha_candle = {
            "open": ha_open,
            "close": ha_close,
            "high": ha_high,
            "low": ha_low,
            "timestamp": c["start"]
        }
        ha_candles.append(ha_candle)
        ha_open = (ha_open + ha_close) / 2
    return ha_candles

def get_recent_candles(session, interval, limit=2):
    res = session.get_kline(category="linear", symbol=symbol, interval=interval, limit=limit)
    candles = []
    for r in res["result"]["list"]:
        candles.append({
            "start": int(r[0]),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4])
        })
    candles.reverse()  # earliest first
    return candles

def calculate_tp_sl(entry, sl, is_buy):
    rr = abs(entry - sl)
    tp = entry + rr if is_buy else entry - rr
    tp += (0.0007 * entry) if is_buy else -(0.0007 * entry)
    return round(tp, 5), round(sl, 5)

def get_usdt_balance(session):
    data = session.get_wallet_balance(accountType="UNIFIED")
    coins = data["result"]["list"][0]["coin"]
    usdt = next((x for x in coins if x["coin"] == "USDT"), None)
    return float(usdt["equity"]) if usdt else 0

async def monitor():
    global buy_window_until, sell_window_until, confirmed_buy_level, confirmed_sell_level

    last_buy_low = None
    last_sell_high = None

    while True:
        try:
            now = datetime.utcnow()

            # === 1 hour check ===
            candles_1h = get_recent_candles(main_session, "60")
            ha_1h = get_heikin_ashi(candles_1h)[-1]

            open_price = ha_1h["open"]
            current_price = ha_1h["close"]

            # Check for break above/below open
            if current_price > open_price:
                if confirmed_buy_level is None or ha_1h["low"] > (last_buy_low or 0):
                    confirmed_buy_level = open_price
                    buy_window_until = (now + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
                    last_buy_low = ha_1h["low"]
                    print(f"✅ Buy level confirmed at {confirmed_buy_level}. Window until {buy_window_until}")

            elif current_price < open_price:
                if confirmed_sell_level is None or ha_1h["high"] < (last_sell_high or float("inf")):
                    confirmed_sell_level = open_price
                    sell_window_until = (now + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
                    last_sell_high = ha_1h["high"]
                    print(f"✅ Sell level confirmed at {confirmed_sell_level}. Window until {sell_window_until}")

            # === 5-minute check ===
            candles_5m = get_recent_candles(main_session, "5")
            ha_5m = get_heikin_ashi(candles_5m)[-1]
            current_5m_close = ha_5m["close"]

            if confirmed_buy_level and now < buy_window_until and current_5m_close > confirmed_buy_level:
                await execute_trade("buy", ha_5m["low"])
                confirmed_buy_level = None  # only use once

            if confirmed_sell_level and now < sell_window_until and current_5m_close < confirmed_sell_level:
                await execute_trade("sell", ha_5m["high"])
                confirmed_sell_level = None  # only use once

        except Exception as e:
            print("❌ Monitor error:", e)

        await asyncio.sleep(300)  # every 5 minutes

async def execute_trade(side, sequence_level):
    try:
        session = sub_session if side == "buy" else main_session
        label = "Sub" if side == "buy" else "Main"

        total_balance = get_usdt_balance(main_session) + get_usdt_balance(sub_session)
        account_balance = get_usdt_balance(session)
        risk_amount = total_balance * 0.10
        fallback_balance = account_balance * 0.90

        qty_usdt = risk_amount if account_balance >= risk_amount else fallback_balance

        current_price = float(session.get_tickers(category="linear", symbol=symbol)["result"]["list"][0]["lastPrice"])
        sl_price = sequence_level
        tp_price, sl_price = calculate_tp_sl(current_price, sl_price, is_buy=(side == "buy"))

        sl_diff = abs(current_price - sl_price)
        leverage = 75
        qty_estimated = qty_usdt / sl_diff
        max_qty = ((account_balance * leverage) / current_price) * 0.9
        qty = max(1, round(min(qty_estimated, max_qty)))

        print(f"🚨 Placing {side.upper()} market order. Qty: {qty}, Entry: {current_price}, SL: {sl_price}, TP: {tp_price}")

        order_res = session.place_order(
            category="linear",
            symbol=symbol,
            side="Buy" if side == "buy" else "Sell",
            order_type="Market",
            qty=str(qty),
            position_idx=0
        )
        print(f"✅ {label} Market order placed:", order_res)

        # Place TP and SL orders
        tick_size = float(session.get_instruments_info(category="linear", symbol=symbol)['result']['list'][0]['priceFilter']['tickSize'])
        round_price = lambda x: round(round(x / tick_size) * tick_size, 8)

        tp_price_rounded = round_price(tp_price)
        sl_price_rounded = round_price(sl_price)

        for price_level in [tp_price_rounded, sl_price_rounded]:
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

        print(f"🎯 TP and 🛡️ SL orders placed: TP={tp_price_rounded}, SL={sl_price_rounded}")

    except Exception as e:
        print("❌ Trade execution error:", e)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor())

@app.get("/")
async def health():
    return {"status": "Bot is running ✅"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
    
