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
def place_conditional_order(session, side="Buy", qty=19, price=0.27895, trigger_price=0.2789):
    try:
        symbol = "TRXUSDT"
        order_type = "Limit"  # After trigger, order will be limit
        position_idx = 0      # 0 = default, 1 = long only, 2 = short only

        response = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,                # Limit price to place after trigger
            trigger_price=trigger_price,
            trigger_by="LastPrice",     # Trigger condition (can also use "MarkPrice")
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
        side = data.get("side", "Buy")
        qty = data.get("qty", 19)
        price = data.get("price", 0.27895)
        trigger_price = data.get("trigger_price", 0.2789)

        res = place_conditional_order(main_session, side=side, qty=qty, price=price, trigger_price=trigger_price)

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
    
