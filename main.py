from fastapi import FastAPI
from pybit.unified_trading import HTTP
import os

app = FastAPI()

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

symbol = "TRXUSDT"
side = "Buy"
entry = 0.2859
tp = 0.2861
sl = 0.2857

def cancel_all_orders(session):
    try:
        session.cancel_all_orders(category="linear", symbol=symbol)
        print("✅ All open orders cancelled")
    except Exception as e:
        print("⚠️ Cancel orders failed:", e)

def get_usdt_balance(session):
    try:
        data = session.get_wallet_balance(accountType="UNIFIED")
        coins = data["result"]["list"][0]["coin"]
        usdt = next((x for x in coins if x["coin"] == "USDT"), None)
        return float(usdt["equity"]) if usdt else 0
    except:
        return 0

def place_main_order():
    try:
        session = main_session

        cancel_all_orders(session)

        # Get price
        price = float(session.get_tickers(category="linear", symbol=symbol)["result"]["list"][0]["lastPrice"])
        immediate_market = (price > entry if side == "Buy" else price < entry)

        balance = get_usdt_balance(session)
        risk_amount = balance * 0.10
        sl_diff = abs(entry - sl)
        leverage = 75
        qty_risk = risk_amount / sl_diff
        max_qty = ((balance * leverage) / entry) * 0.9
        qty = max(1, round(min(qty_risk, max_qty)))

        print(f"📢 Placing {side} market order at {entry}, qty={qty}")

        res = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            reduce_only=False,
            close_on_trigger=False,
            position_idx=0,
            time_in_force="ImmediateOrCancel"
        )
        print("✅ Entry order placed:", res)

        tick_size = float(session.get_instruments_info(category="linear", symbol=symbol)['result']['list'][0]['priceFilter']['tickSize'])
        round_price = lambda x: round(round(x / tick_size) * tick_size, 8)

        tp_price = round_price(tp)
        sl_price = round_price(sl)

        session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            order_type="Limit",
            price=tp_price,
            qty=qty,
            reduce_only=True,
            time_in_force="GoodTillCancel",
            close_on_trigger=True,
            position_idx=0
        )
        print(f"✅ TP order placed at {tp_price}")

        session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            order_type="Limit",
            price=sl_price,
            qty=qty,
            reduce_only=True,
            time_in_force="GoodTillCancel",
            close_on_trigger=True,
            position_idx=0
        )
        print(f"✅ SL order placed at {sl_price}")

        print("🎉 Done.")

    except Exception as e:
        print("❌ Failed to place order:", e)

@app.on_event("startup")
async def startup_event():
    place_main_order()

@app.get("/")
def health():
    return {"status": "Bot is online ✅"}
    
