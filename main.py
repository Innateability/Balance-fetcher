from fastapi import FastAPI
import os
from pybit.unified_trading import HTTP
import uvicorn

app = FastAPI()

# === API keys from environment ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

# Initialize Bybit session
session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

@app.get("/")
async def root():
    return {"status": "Service is running ✅"}

@app.on_event("startup")
async def place_conditional_order_on_startup():
    try:
        # Get balance before placing order
        balance_data = session.get_wallet_balance(accountType="UNIFIED")
        coins = balance_data["result"]["list"][0]["coin"]
        usdt = next((x for x in coins if x["coin"] == "USDT"), None)

        if not usdt:
            print("⚠️ USDT balance not found.")
            return

        # ✅ Use equity instead of availableBalance
        available = float(usdt["equity"]) if usdt and usdt.get("equity") else 0.0
        print(f"💰 Available USDT before placing order: {available:.6f}")

        # Order parameters
        price = 0.28        # Limit price
        qty = 20
        trigger_price = 0.29 # Trigger price
        leverage = 75

        notional_value = price * qty
        required_margin = notional_value / leverage

        print(f"📄 Required initial margin: {required_margin:.6f}")

        if available >= required_margin:
            # Place conditional limit order
            res = session.place_order(
                category="linear",
                symbol="TRXUSDT",
                side="Sell",
                order_type="Limit",
                qty=str(qty),
                price=str(price),
                trigger_price=str(trigger_price),
                trigger_direction=1,  # 1 = triggers when price rises above trigger price
                time_in_force="GTC",
                reduce_only=False,
                close_on_trigger=False
            )
            print("✅ Order placed successfully:", res)
        else:
            print("⚠️ Not enough margin to place order.")

        # Get balance after placing order
        balance_data_after = session.get_wallet_balance(accountType="UNIFIED")
        coins_after = balance_data_after["result"]["list"][0]["coin"]
        usdt_after = next((x for x in coins_after if x["coin"] == "USDT"), None)
        available_after = float(usdt_after["equity"]) if usdt_after and usdt_after.get("equity") else 0.0

        print(f"💰 Available USDT after operation: {available_after:.6f}")

    except Exception as e:
        print("❌ Error placing order:", e)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
    
