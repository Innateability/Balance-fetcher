from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pybit.unified_trading import HTTP
import os
import asyncio
from datetime import datetime

app = FastAPI()

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")
SUB_UID = os.getenv("SUB_UID")

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

# === State tracking ===
state = {
    "buy": {"entry": None, "monitoring": False, "active": False},
    "sell": {"entry": None, "monitoring": False, "active": False},
    "high": None,
    "low": None
}

# === Utility functions ===
def get_usdt_balance(session):
    try:
        data = session.get_wallet_balance(accountType="UNIFIED")
        coins = data["result"]["list"][0]["coin"]
        usdt = next((x for x in coins if x["coin"] == "USDT"), None)
        return float(usdt["equity"]) if usdt else 0
    except:
        return 0

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
        print("🔁 Rebalanced main/sub")
    except Exception as e:
        print("❌ Rebalance failed:", e)

def cancel_all_orders(session):
    try:
        session.cancel_all_orders(category="linear", symbol="TRXUSDT")
        print("❌ All open orders cancelled for TRXUSDT")
    except Exception as e:
        print("⚠️ Failed to cancel orders:", e)

def close_all_positions(session, label):
    try:
        pos = session.get_positions(category="linear", symbol="TRXUSDT")["result"]["list"]
        for p in pos:
            size = float(p["size"])
            side = p["side"]
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
                print(f"✅ {label} account: Closed {side} {size}")
        rebalance_funds()
    except Exception as e:
        print(f"❌ {label} close failed:", e)

async def monitor_prices(side):
    session = sub_session if side == "buy" else main_session
    label = "Sub" if side == "buy" else "Main"
    while state[side]["monitoring"]:
        try:
            price_data = session.get_tickers(category="linear", symbol="TRXUSDT")
            price = float(price_data["result"]["list"][0]["lastPrice"])
            entry = state[side]["entry"]

            if (side == "buy" and price >= entry) or (side == "sell" and price <= entry):
                if state[side]["active"]:
                    print(f"⚠️ Already has active {side} trade. Skipping execution.")
                    return

                print(f"🚀 Entry price hit for {side.upper()} at {price}")

                # Calculate SL
                sl = state["low"] if side == "buy" else state["high"]
                rr = abs(entry - sl)
                tp_base = entry + 1.5 * rr if side == "buy" else entry - 1.5 * rr
                tp = tp_base + (0.007 * entry) if side == "buy" else tp_base - (0.007 * entry)

                balance = get_usdt_balance(session)
                total = get_usdt_balance(main_session) + get_usdt_balance(sub_session)
                risk = total * 0.10
                sl_diff = abs(entry - sl)
                leverage = 75
                qty_risk = risk / sl_diff
                max_qty = ((balance * leverage) / entry) * 0.9
                qty = max(1, round(min(qty_risk, max_qty)))

                # Cancel and close before placing new
                cancel_all_orders(session)
                close_all_positions(session, label)

                # Open market order
                session.place_order(
                    category="linear",
                    symbol="TRXUSDT",
                    side="Buy" if side == "buy" else "Sell",
                    order_type="Market",
                    qty=qty,
                    reduce_only=False,
                    position_idx=0
                )
                print(f"✅ Market {side} order placed with qty {qty}")

                # TP and SL orders
                session.place_order(
                    category="linear",
                    symbol="TRXUSDT",
                    side="Sell" if side == "buy" else "Buy",
                    order_type="Limit",
                    price=tp,
                    qty=qty,
                    reduce_only=True,
                    time_in_force="GoodTillCancel",
                    close_on_trigger=True,
                    position_idx=0
                )
                session.place_order(
                    category="linear",
                    symbol="TRXUSDT",
                    side="Sell" if side == "buy" else "Buy",
                    order_type="Limit",
                    price=sl,
                    qty=qty,
                    reduce_only=True,
                    time_in_force="GoodTillCancel",
                    close_on_trigger=True,
                    position_idx=0
                )
                print(f"✅ TP at {tp} and SL at {sl} set.")

                state[side]["active"] = True
                state[side]["monitoring"] = False
                break

        except Exception as e:
            print("❌ Monitor error:", e)
        await asyncio.sleep(5)

# === API endpoints ===
@app.post("/signal")
async def receive_signal(request: Request):
    try:
        body = (await request.body()).decode().strip()
        print("\n📩 Signal received:\n", body)
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        symbol = lines[0].upper()
        if symbol != "TRXUSDT":
            return JSONResponse(content={"error": "Unsupported symbol"}, status_code=400)

        # Check if it's high/low update
        if any("high:" in line.lower() for line in lines) and any("low:" in line.lower() for line in lines):
            for line in lines:
                if "high:" in line.lower():
                    state["high"] = float(line.split(":")[1])
                elif "low:" in line.lower():
                    state["low"] = float(line.split(":")[1])
            print(f"✅ Updated high={state['high']} low={state['low']}")
            return {"status": "High/Low updated"}

        # Entry signal
        signal_type = lines[1].split()[1].strip().lower()  # Type buy or Type sell
        entry = float(lines[2].split(":")[1].strip())
        side = "buy" if signal_type == "buy" else "sell"

        # If no active trade, update entry and start monitoring
        if not state[side]["active"]:
            state[side]["entry"] = entry
            state[side]["monitoring"] = True
            print(f"👀 Now monitoring for {side.upper()} entry at {entry}")
            asyncio.create_task(monitor_prices(side))
            return {"status": f"Monitoring for {side.upper()} entry at {entry}"}
        else:
            return JSONResponse(content={"error": f"{side.upper()} trade already active"}, status_code=400)

    except Exception as e:
        print("❌ Error:", e)
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/")
def health():
    return {"status": "Bot is online ✅"}
