from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
import os

app = FastAPI()

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")
SUB_UID = os.getenv("SUB_UID")

# === BYBIT SESSIONS ===
main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

# === Get USDT balance ===
def get_usdt_balance(session):
    try:
        data = session.get_wallet_balance(accountType="UNIFIED")
        coins = data["result"]["list"][0]["coin"]
        usdt = next((c for c in coins if c["coin"] == "USDT"), None)
        return float(usdt["equity"]) if usdt else 0.0
    except:
        return 0.0

# === Rebalance Funds ===
def rebalance_funds():
    try:
        main = get_usdt_balance(main_session)
        sub = get_usdt_balance(sub_session)
        total = main + sub
        target = total / 2

        if abs(main - sub) < 0.1:
            print("✅ Balance already even.")
            return

        amount = abs(main - target)
        transfer_type = "MAIN_SUB" if main > target else "SUB_MAIN"

        main_session.create_internal_transfer(
            transfer_type=transfer_type,
            coin="USDT",
            amount=str(round(amount, 2)),
            sub_member_id=SUB_UID
        )

        print("🔁 Rebalanced funds between main and sub accounts")
    except Exception as e:
        print("❌ Rebalance failed:", e)

# === Close all trades ===
def close_trades(session, label="Main"):
    try:
        positions = session.get_positions(category="linear", symbol="TRXUSDT")["result"]["list"]
        closed = False

        for pos in positions:
            side = pos["side"]
            size = float(pos["size"])

            if size > 0:
                close_side = "Sell" if side == "Buy" else "Buy"
                session.place_order(
                    category="linear",
                    symbol="TRXUSDT",
                    side=close_side,
                    order_type="Market",
                    qty=size,
                    reduce_only=True,
                    position_idx=0
                )
                print(f"✅ {label} Account: Closed {side} position of size {size}")
                closed = True

        if not closed:
            print(f"ℹ️ {label} Account: No open positions to close.")
        return True

    except Exception as e:
        print(f"❌ {label} Account: Failed to close positions -", str(e))
        return False

# === POST /signal ===
@app.post("/signal")
async def receive_signal(request: Request):
    try:
        message = (await request.body()).decode().strip()
        print("\n📩 Received Signal:\n", message)

        lines = message.splitlines()
        if len(lines) < 3:
            return {"error": "Invalid signal format"}

        symbol = lines[0].strip().upper()
        type_line = lines[1].lower()

        if symbol != "TRXUSDT":
            return {"error": "Unsupported symbol"}

        if "type: sell" in type_line:
            closed = close_trades(main_session, label="Main")
        elif "type: buy" in type_line:
            closed = close_trades(sub_session, label="Sub")
        else:
            return {"error": "Unknown signal type"}

        if closed:
            rebalance_funds()
            return {"status": "Trades closed and balance rebalanced"}
        else:
            return {"status": "No trades to close"}

    except Exception as e:
        print("❌ Error:", str(e))
        return {"error": str(e)}

# === Health Check ===
@app.get("/")
def root():
    return {"status": "Bot is online"
