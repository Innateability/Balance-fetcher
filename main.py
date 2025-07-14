from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
import os
import uvicorn

app = FastAPI()

# === API keys ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

# === Global settings ===
symbol = "TRXUSDT"
qty = 20
tp_price = 0.3016
sl_price = 0.3013

@app.get("/")
async def root():
    return {"status": "Bot is online ✅"}

@app.on_event("startup")
async def place_market_and_protective_orders():
    global tp_price, sl_price

    try:
        # Place market buy order
        res = session.place_order(
            category="linear",
            symbol=symbol,
            side="Buy",
            order_type="Market",
            qty=qty,
            reduce_only=False,
            position_idx=0
        )
        print("✅ Market buy order placed:", res)

        # Place TP order
        tp_res = session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell",
            order_type="Limit",
            price=str(tp_price),
            qty=qty,
            reduce_only=True,
            time_in_force="GTC",
            close_on_trigger=True,
            position_idx=0
        )
        print("🎯 TP order placed:", tp_res)

        # Place SL order
        sl_res = session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell",
            order_type="Limit",
            price=str(sl_price),
            qty=qty,
            reduce_only=True,
            time_in_force="GTC",
            close_on_trigger=True,
            position_idx=0
        )
        print("🛡️ SL order placed:", sl_res)

    except Exception as e:
        print("❌ Error placing initial orders:", e)

@app.post("/update")
async def update_tp_sl(request: Request):
    global tp_price, sl_price

    data = await request.json()
    tp_price = float(data.get("tp"))
    sl_price = float(data.get("sl"))
    print(f"♻️ Received update: TP={tp_price}, SL={sl_price}")

    try:
        # Cancel all open reduce-only orders
        session.cancel_all_orders(category="linear", symbol=symbol)
        print("❌ All existing TP/SL orders cancelled.")

        # Re-create updated TP
        tp_res = session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell",
            order_type="Limit",
            price=str(tp_price),
            qty=qty,
            reduce_only=True,
            time_in_force="GTC",
            close_on_trigger=True,
            position_idx=0
        )
        print("✅ Updated TP order placed:", tp_res)

        # Re-create updated SL
        sl_res = session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell",
            order_type="Limit",
            price=str(sl_price),
            qty=qty,
            reduce_only=True,
            time_in_force="GTC",
            close_on_trigger=True,
            position_idx=0
        )
        print("✅ Updated SL order placed:", sl_res)

        return {"status": "TP and SL updated successfully."}
    except Exception as e:
        print("❌ Error updating TP/SL:", e)
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
