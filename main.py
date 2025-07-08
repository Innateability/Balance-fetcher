from fastapi import FastAPI
import os
from pybit.unified_trading import HTTP

app = FastAPI()

MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

@app.get("/")
def create_limit_order():
    try:
        res = main_session.place_order(
            category="linear",
            symbol="TRXUSDT",
            side="Buy",
            order_type="Limit",
            qty="17",
            price="0.3",
            time_in_force="GTC",   # ✅ FIXED here
            reduce_only=False,
            close_on_trigger=False
        )
        print("✅ Limit order created:", res)
        return {"status": "Limit order placed", "response": res}
    except Exception as e:
        print("❌ Error:", e)
        return {"error": str(e)}
        
