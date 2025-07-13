from fastapi import FastAPI
import os
from pybit.unified_trading import HTTP
import uvicorn

app = FastAPI()

# === API keys ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

@app.get("/")
async def root():
    return {"status": "Service is running ✅"}

@app.on_event("startup")
async def place_order_on_startup():
    try:
        # Order parameters
        qty = 20
        tp = 0.32
        sl = 0.28

        # Place market buy order with attached TP and SL
        res = session.place_order(
            category="linear",
            symbol="TRXUSDT",
            side="Buy",
            order_type="Market",
            qty=str(qty),
            take_profit=str(tp),
            stop_loss=str(sl),
            position_idx=0
        )
        print("✅ Buy order with TP and SL placed:", res)

    except Exception as e:
        print("❌ Error placing order:", e)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
    
