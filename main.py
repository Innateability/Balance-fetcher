from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
import os
import uvicorn
from datetime import datetime, timedelta

app = FastAPI()

# === API KEYS ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")
SUB_UID = os.getenv("SUB_UID")

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

symbol = "TRXUSDT"

buy_window_until = None
sell_window_until = None

# === Balance helpers ===
def get_usdt_balance(session):
    data = session.get_wallet_balance(accountType="UNIFIED")
    coins = data["result"]["list"][0]["coin"]
    usdt = next((x for x in coins if x["coin"] == "USDT"), None)
    return float(usdt["equity"]) if usdt else 0

# === Calculate window close time ===
def calculate_window_expiry():
    now = datetime.utcnow()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    expiry = next_hour + timedelta(hours=1)
    return expiry

@app.get("/")
async def health():
    return {"status": "Bot is online ✅"}

@app.post("/buy")
async def open_buy_window():
    global buy_window_until
    buy_window_until = calculate_window_expiry()
    print(f"🟢 Buy window open until {buy_window_until} UTC")
    return {"status": f"Buy window open until {buy_window_until} UTC"}

@app.post("/sell")
async def open_sell_window():
    global sell_window_until
    sell_window_until = calculate_window_expiry()
    print(f"🔴 Sell window open until {sell_window_until} UTC")
    return {"status": f"Sell window open until {sell_window_until} UTC"}

@app.post("/entry")
async def receive_entry(request: Request):
    global buy_window_until, sell_window_until

    text = (await request.body()).decode()
    print("\n📩 Signal received:\n", text)

    try:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not any("Entry" in l for l in lines):
            return {"error": "Entry header missing"}

        type_line = next(l for l in lines if l.lower().startswith("type"))
        entry_type = int(type_line.split(":")[1].strip())

        buy_sl = float(next(l.split(":")[1].strip() for l in lines if l.lower().startswith("buy sl")))
        buy_tp = float(next(l.split(":")[1].strip() for l in lines if l.lower().startswith("buy tp")))
        sell_sl = float(next(l.split(":")[1].strip() for l in lines if l.lower().startswith("sell sl")))
        sell_tp = float(next(l.split(":")[1].strip() for l in lines if l.lower().startswith("sell tp")))

        now = datetime.utcnow()

        if entry_type == 0:
            if not buy_window_until or now > buy_window_until:
                return {"status": "Buy window not active."}
            await execute_trade("buy", buy_sl, buy_tp)
            return {"status": "Buy trade executed."}

        elif entry_type == 1:
            if not sell_window_until or now > sell_window_until:
                return {"status": "Sell window not active."}
            await execute_trade("sell", sell_sl, sell_tp)
            return {"status": "Sell trade executed."}

        else:
            return {"error": "Invalid Type value"}

    except Exception as e:
        print("❌ Error parsing signal:", e)
        return {"error": str(e)}

async def execute_trade(side, sl_price, tp_price):
    try:
        session = sub_session if side == "buy" else main_session
        label = "Sub" if side == "buy" else "Main"

        total_balance = get_usdt_balance(main_session) + get_usdt_balance(sub_session)
        account_balance = get_usdt_balance(session)
        risk_amount = total_balance * 0.10
        fallback_balance = account_balance * 0.90

        qty_usdt = risk_amount if account_balance >= risk_amount else fallback_balance

        current_price = float(session.get_tickers(category="linear", symbol=symbol)["result"]["list"][0]["lastPrice"])
        sl_diff = abs(current_price - sl_price)
        leverage = 75
        qty_estimated = qty_usdt / sl_diff
        max_qty = ((account_balance * leverage) / current_price) * 0.9
        qty = max(1, round(min(qty_estimated, max_qty)))

        print(f"Placing {side.upper()} market order. Qty: {qty}, Entry: {current_price}")

        # Place market order
        order_res = session.place_order(
            category="linear",
            symbol=symbol,
            side="Buy" if side == "buy" else "Sell",
            order_type="Market",
            qty=str(qty),
            position_idx=0
        )
        print(f"✅ {label} Market order placed:", order_res)

        # TP and SL reduce-only orders
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
        print("❌ Failed to execute trade:", e)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
    
