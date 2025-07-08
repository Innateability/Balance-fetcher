from fastapi import FastAPI
from pybit.unified_trading import HTTP
import os

app = FastAPI()

# === Load MAIN keys from environment ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

# === Create Bybit session using MAIN account ===
main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

@app.get("/")
def place_buy_limit_order():
    try:
        # === Order parameters ===
        symbol = "TRXUSDT"
        side = "Buy"
        order_type = "Limit"
        price = 0.3
        qty = 20

        # === Create the limit order ===
        response = main_session.place_order(
            category="linear",      # USDT perpetual
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            time_in_force="GoodTillCancel",
            reduce_only=False,
            close_on_trigger=False
        )
        print("✅ Buy limit order created:", response)
        return {"status": "Buy limit order created", "details": response}

    except Exception as e:
        print("❌ Error:", e)
        return {"error": str(e)
