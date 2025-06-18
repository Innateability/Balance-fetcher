from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
import os

app = FastAPI()

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")

# === BYBIT SESSIONS ===
main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

# === UTILITY FUNCTIONS ===
def close_all_positions(session, label):
    try:
        positions = session.get_positions(category="linear")["result"]["list"]
        for p in positions:
            size = float(p["size"])
            if size > 0:
                symbol = p["symbol"]
                side = "Buy" if p["side"] == "Sell" else "Sell"
                session.place_order(
                    category="linear",
                    symbol=symbol,
                    side=side,
                    order_type="Market",
                    qty=size,
                    reduce_only=True,
                    position_idx=0
                )
                print(f"✅ {label}: Closed {size} contracts on {symbol}")
    except Exception as e:
        print(f"❌ {label}: Failed to close positions -", e)

def get_usdt_balance(session):
    try:
        balances = session.get_wallet_balance(accountType="UNIFIED")["result"]["list"]
        for b in balances:
            if b["coin"] == "USDT":
                return float(b["availableBalance"])
        return 0.0
    except Exception as e:
        print("❌ Failed to get USDT balance:", e)
        return 0.0

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

        # ✅ Get sub UID from main session
        sub_id = main_session.get_sub_uid()["result"]["subMemberIds"][0]["subMemberId"]
        transfer_type = "MAIN_SUB" if main > target else "SUB_MAIN"

        main_session.create_internal_transfer(
            transfer_type=transfer_type,
            coin="USDT",
            amount=str(round(amount, 2)),
            sub_member_id=sub_id
        )

        print(f"🔁 Rebalanced: Transferred {amount:.2f} USDT ({transfer_type})")
    except Exception as e:
        print("❌ Rebalance failed:", e)

# === SIGNAL ENDPOINT ===
@app.post("/signal")
async def handle_signal(request: Request):
    try:
        body = (await request.body()).decode()
        print("\n📩 Received Signal:\n", body)

        lines = body.strip().splitlines()
        if len(lines) < 2:
            return {"error": "Invalid signal format"}

        symbol = lines[0].strip()
        data = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip().lower()] = v.strip()

        signal_type = data.get("type", "").lower()
        if signal_type not in ["buy", "sell"]:
            return {"error": "Invalid signal type"}

        if signal_type == "sell":
            close_all_positions(main_session, "Main Account")
        elif signal_type == "buy":
            close_all_positions(sub_session, "Sub Account")

        rebalance_funds()

        return {"status": "Closed trades and rebalanced funds."}

    except Exception as e:
        print("❌ Error handling signal:", e)
        return {"error": str(e)}

# === HEALTH CHECK ===
@app.get("/")
def root():
    return {"status": "Bot is running"}
