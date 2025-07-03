from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pybit.unified_trading import HTTP
import os

app = FastAPI()

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

# === Create Bybit session ===
main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

# === Place Conditional Order ===
def place_conditional_order(session, side="Sell", qty=18, price=0.287, trigger_price=0.2865):
    try:
        symbol = "TRXUSDT"
        order_type = "Limit"      # The type of order placed after trigger
        position_idx = 0          # 0 = default (one-way), 1 = long only, 2 = short only

        # Choose trigger_direction
        if side == "Buy":
            trigger_direction = 1  # Trigger when price rises to or above trigger_price
        else:
            trigger_direction = 2  # Trigger when price falls to or below trigger_price

        response = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            trigger_price=trigger_price,
            trigger_direction=trigger_direction,
            trigger_by="LastPrice",     # Could also use "MarkPrice"
            time_in_force="GoodTillCancel",
            reduce_only=False,
            close_on_trigger=False,
            position_idx=position_idx
        )
        return response

    except Exception as e:
        print("❌ Exception while placing conditional order:", e)
        return None

# === API Route to create conditional order ===
@app.post("/conditional-order")
async def create_conditional_order(request: Request):
    try:
        data = await request.json()
        side = data.get("side", "Sell")
        qty = data.get("qty", 18)
        price = data.get("price", 0.287)
        trigger_price = data.get("trigger_price", 0.2865)

        res = place_conditional_order(
            main_session,
            side=side,
            qty=qty,
            price=price,
            trigger_price=trigger_price
        )

        if res:
            print("🔎 Full API response:", res)

        if res and res["retCode"] == 0:
            return {"status": "✅ Conditional order created", "data": res["result"]}
        else:
            return JSONResponse(content={"error": res["retMsg"] if res else "No response"}, status_code=500)

    except Exception as e:
        print("❌ FastAPI route error:", e)
        return JSONResponse(content={"error": str(e)}, status_code=500)

# === Health Check ===
@app.get("/")
def health():
    return {"status": "Bot is online ✅"}
    
