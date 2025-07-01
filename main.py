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
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SUB_UID = os.getenv("SUB_UID")

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

# === Place Conditional Buy Order ===
def place_conditional_buy(session):
    try:
        symbol = "TRXUSDT"
        side = "Buy"
        order_type = "Limit"     # Order type after triggered
        qty = 19
        trigger_price = 0.2789
        price = 0.27895
        order_price_type = "Limit"
        position_idx = 1        # 1 = one-way mode, 2 = hedge

        response = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            trigger_direction=1,  # 1 = trigger above market price, 2 = below
            trigger_price=trigger_price,
            reduce_only=False,
            close_on_trigger=False,
            order_price_type=order_price_type,
            time_in_force="GoodTillCancel",
            position_idx=position_idx
        )
        return response

    except Exception as e:
        print("❌ Exception while placing order:", e)
        return None

@app.post("/conditional-buy")
async def create_conditional_buy(request: Request):
    try:
        res = place_conditional_buy(main_session)

        # Debug print to see full response
        if res:
            print("🔎 Full API response:", res)

        if res and res["retCode"] == 0:
            return {"status": "✅ Conditional buy order created", "data": res["result"]}
        else:
            # Show Bybit error message if available
            return JSONResponse(content={"error": res["retMsg"] if res else "No response"}, status_code=500)

    except Exception as e:
        print("❌ FastAPI route error:", e)
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/")
def health():
    return {"status": "Bot is online ✅"}
    
