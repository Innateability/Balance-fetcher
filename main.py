from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pybit.unified_trading import HTTP
import os

app = FastAPI()

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

# === Place Conditional Buy Order ===
def place_conditional_buy(session):
    try:
        symbol = "TRXUSDT"
        side = "Buy"
        order_type = "Limit"          # Order type after triggered
        qty = 19
        trigger_price = 0.2789
        price = 0.27895
        position_idx = 1  # 1 = one-way (default)

        response = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            trigger_price=trigger_price,
            trigger_by="LastPrice",
            time_in_force="GoodTillCancel",
            reduce_only=False,
            close_on_trigger=False,
            position_idx=position_idx
        )
        return response

    except Exception as e:
        print("❌ Exception while placing conditional order:", e)
        return None

# === Place Market Order ===
def place_market_order(session):
    try:
        symbol = "TRXUSDT"
        side = "Buy"   # or "Sell"
        qty = 19
        position_idx = 1  # 1 = one-way (default)

        response = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            reduce_only=False,
            close_on_trigger=False,
            position_idx=position_idx,
            time_in_force="ImmediateOrCancel"
        )
        return response

    except Exception as e:
        print("❌ Exception while placing market order:", e)
        return None

# === Route to create conditional buy ===
@app.post("/conditional-buy")
async def create_conditional_buy(request: Request):
    try:
        res = place_conditional_buy(main_session)

        if res:
            print("🔎 Full API response:", res)

        if res and res["retCode"] == 0:
            return {"status": "✅ Conditional buy order created", "data": res["result"]}
        else:
            return JSONResponse(content={"error": res["retMsg"] if res else "No response"}, status_code=500)

    except Exception as e:
        print("❌ FastAPI route error:", e)
        return JSONResponse(content={"error": str(e)}, status_code=500)

# === Route to create market order ===
@app.post("/market-buy")
async def create_market_buy(request: Request):
    try:
        res = place_market_order(main_session)

        if res:
            print("🔎 Full API response:", res)

        if res and res["retCode"] == 0:
            return {"status": "✅ Market buy order created", "data": res["result"]}
        else:
            return JSONResponse(content={"error": res["retMsg"] if res else "No response"}, status_code=500)

    except Exception as e:
        print("❌ FastAPI route error:", e)
        return JSONResponse(content={"error": str(e)}, status_code=500)

# === Health Check ===
@app.get("/")
def health():
    return {"status": "Bot is online ✅"}
