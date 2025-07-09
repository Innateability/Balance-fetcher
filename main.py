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
        # Get USDT balance before placing order
        balance_data = session.get_wallet_balance(accountType="UNIFIED")
        coins = balance_data["result"]["list"][0]["coin"]
        usdt = next((x for x in coins if x["coin"] == "USDT"), None)

        # Use walletBalance instead of availableToWithdraw
        available = float(usdt["walletBalance"]) if usdt and usdt["walletBalance"] else 0.0

        print(f"Available USDT before placing order: {available:.6f}")

        # Calculate required initial margin for 20 TRX at 0.3 with 75x leverage
        price = 0.3
        qty = 20
        leverage = 75

        notional_value = price * qty
        required_margin = notional_value / leverage

        print(f"📄 Required initial margin: {required_margin:.6f}")

        if available >= required_margin:
            # Place limit order
            res = session.place_order(
                category="linear",
                symbol="TRXUSDT",
                side="Buy",
                order_type="Limit",
                qty=str(qty),
                price=str(price),
                time_in_force="GTC",
                reduce_only=False,
                close_on_trigger=False
            )
            print("✅ Order response:", res)
        else:
            print("⚠️ Not enough margin to place order.")

        # Fetch balance again after operation
        balance_data_after = session.get_wallet_balance(accountType="UNIFIED")
        coins_after = balance_data_after["result"]["list"][0]["coin"]
        usdt_after = next((x for x in coins_after if x["coin"] == "USDT"), None)
        available_after = float(usdt_after["walletBalance"]) if usdt_after and usdt_after["walletBalance"] else 0.0

        print(f"💰 Available USDT after operation: {available_after:.6f}")

    except Exception as e:
        print("❌ Error placing order:", e)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
