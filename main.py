from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
import os

app = FastAPI()

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

# === BYBIT SESSION ===
main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

# === Close all open positions ===
def close_all_trades():
    try:
        positions = main_session.get_positions(category="linear", symbol="TRXUSDT")["result"]["list"]
        closed_any = False

        for pos in positions:
            side = pos["side"]  # "Buy" or "Sell"
            size = float(pos["size"])

            if size > 0:
                close_side = "Sell" if side == "Buy" else "Buy"
                main_session.place_order(
                    category="linear",
                    symbol="TRXUSDT",
                    side=close_side,
                    order_type="Market",
                    qty=size,
                    reduce_only=True,
                    position_idx=0
                )
                closed_any = True
                print(f"✅ Closed {side} position of size {size}")

        if not closed_any:
            print("ℹ️ No open positions to close.")
        return {"status": "Checked positions", "action": "Closed if any"}
    except Exception as e:
        print("❌ Error closing positions:", e)
        return {"error": str(e)}

# === POST /signal ===
@app.post("/signal")
async def signal_receiver(request: Request):
    try:
        message = (await request.body()).decode().strip()
        print("\n📩 Received signal:\n", message)

        lines = message.splitlines()
        if len(lines) < 3:
            return {"error": "Invalid signal format"}

        symbol = lines[0].strip().upper()
        type_line = lines[1].lower()
        tp_line = lines[2].lower()
        sl_line = lines[3].lower() if len(lines) > 3 else ""

        if symbol != "TRXUSDT":
            return {"error": "Unsupported symbol"}

        if not ("type: sell" in type_line or "type: buy" in type_line):
            return {"error": "Invalid type"}

        return close_all_trades()

    except Exception as e:
        return {"error": str(e)}

# === Health Check ===
@app.get("/")
def root():
    return {"status": "Bot is online"}
    
