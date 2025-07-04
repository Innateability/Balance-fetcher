from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pybit.unified_trading import HTTP
import os
import asyncio

app = FastAPI()

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")
SUB_UID = os.getenv("SUB_UID")

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

# === Global State ===
last_levels = {"high": None, "low": None}
active_trade = {"side": None, "entry": None, "tp": None, "sl": None, "qty": None}
monitoring = False

# === Balance Helpers ===
def get_usdt_balance(session):
    try:
        data = session.get_wallet_balance(accountType="UNIFIED")
        coins = data["result"]["list"][0]["coin"]
        usdt = next((x for x in coins if x["coin"] == "USDT"), None)
        return float(usdt["equity"]) if usdt else 0
    except Exception as e:
        print("❌ Balance error:", e)
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

# === Get current price ===
async def get_current_price():
    try:
        tick = main_session.get_tickers(category="linear", symbol="TRXUSDT")
        price = float(tick["result"]["list"][0]["lastPrice"])
        return price
    except Exception as e:
        print("❌ Price fetch error:", e)
        return None

# === Monitor and open logic ===
async def monitor_and_open():
    global monitoring, active_trade
    monitoring = True
    session = sub_session if active_trade["side"] == "buy" else main_session

    while True:
        await asyncio.sleep(5)

        # Check if there's an open position already
        pos = session.get_positions(category="linear", symbol="TRXUSDT")["result"]["list"]
        open_size = sum(float(p["size"]) for p in pos)
        if open_size > 0:
            print("⚠️ Already in a position. Stopping monitoring.")
            monitoring = False
            return

        price = await get_current_price()
        if not price:
            continue

        print(f"🔎 Current price: {price} | Waiting for entry: {active_trade['entry']}")

        if (active_trade["side"] == "buy" and price >= active_trade["entry"]) or \
           (active_trade["side"] == "sell" and price <= active_trade["entry"]):

            print("✅ Entry condition met. Opening market order.")

            # Calculate balance & qty
            balance = get_usdt_balance(session)
            total = get_usdt_balance(main_session) + get_usdt_balance(sub_session)
            risk = total * 0.10
            sl_diff = abs(active_trade["entry"] - active_trade["sl"])
            leverage = 75
            qty_risk = risk / sl_diff
            max_qty = ((balance * leverage) / active_trade["entry"]) * 0.9
            qty = max(1, round(min(qty_risk, max_qty)))

            active_trade["qty"] = qty

            # Place market entry
            session.place_order(
                category="linear",
                symbol="TRXUSDT",
                side="Buy" if active_trade["side"] == "buy" else "Sell",
                order_type="Market",
                qty=qty,
                reduce_only=False,
                position_idx=0
            )
            print(f"📥 Opened market {active_trade['side']} order with qty={qty}")

            # Start price monitoring for exit
            await monitor_exit(session)
            return

# === Monitor exit ===
async def monitor_exit(session):
    global active_trade, monitoring

    while True:
        await asyncio.sleep(5)
        price = await get_current_price()
        if not price:
            continue

        print(f"🔎 Price: {price} | TP: {active_trade['tp']} | SL: {active_trade['sl']}")

        if (active_trade["side"] == "buy" and (price >= active_trade["tp"] or price <= active_trade["sl"])) or \
           (active_trade["side"] == "sell" and (price <= active_trade["tp"] or price >= active_trade["sl"])):

            print("🏁 TP or SL hit. Closing positions.")
            pos = session.get_positions(category="linear", symbol="TRXUSDT")["result"]["list"]
            for p in pos:
                size = float(p["size"])
                if size > 0:
                    close_side = "Sell" if p["side"] == "Buy" else "Buy"
                    session.place_order(
                        category="linear",
                        symbol="TRXUSDT",
                        side=close_side,
                        order_type="Market",
                        qty=size,
                        reduce_only=True,
                        position_idx=0
                    )
                    print(f"✅ Closed {p['side']} position with size={size}")

            # Rebalance after closing
            rebalance_funds()

            # Clear trade state
            active_trade.update({"side": None, "entry": None, "tp": None, "sl": None, "qty": None})
            monitoring = False
            return

# === API Signal endpoint ===
@app.post("/signal")
async def receive_signal(request: Request):
    global last_levels, active_trade, monitoring

    try:
        body = (await request.body()).decode().strip()
        lines = [l.strip() for l in body.splitlines() if l.strip()]

        if len(lines) < 3:
            return JSONResponse(content={"error": "Bad format"}, status_code=400)

        symbol = lines[0].upper()
        signal_type = lines[1].split(":")[1].strip().lower() if ":" in lines[1] else lines[1].strip().lower()
        entry = float(lines[2].split(":")[1].strip())

        if symbol != "TRXUSDT":
            return JSONResponse(content={"error": "Unsupported symbol"}, status_code=400)

        if monitoring:
            return JSONResponse(content={"error": "Already monitoring an active trade"}, status_code=400)

        side = "buy" if signal_type == "buy" else "sell"

        # Use last_levels for SL
        sl = last_levels["low"] if side == "buy" else last_levels["high"]
        if sl is None:
            return JSONResponse(content={"error": "SL levels missing (high/low signal not set)"}, status_code=400)

        # Calculate RR-based TP
        rr = abs(entry - sl)
        tp = entry + 1.5 * rr + (0.007 * entry) if side == "buy" else entry - 1.5 * rr - (0.007 * entry)

        # Store active trade
        active_trade.update({"side": side, "entry": entry, "tp": tp, "sl": sl, "qty": None})
        print(f"✅ Received signal: Side={side}, Entry={entry}, SL={sl}, TP={tp}")

        # Start monitoring
        asyncio.create_task(monitor_and_open())

        return {"status": f"Started monitoring for {side} entry at {entry}"}

    except Exception as e:
        print("❌ Error:", e)
        return JSONResponse(content={"error": str(e)}, status_code=500)

# === API High/Low update endpoint ===
@app.post("/levels")
async def update_levels(request: Request):
    global last_levels
    try:
        body = (await request.body()).decode().strip()
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        if len(lines) < 3:
            return JSONResponse(content={"error": "Bad format"}, status_code=400)

        symbol = lines[0].upper()
        high = float(lines[1].split(":")[1].strip())
        low = float(lines[2].split(":")[1].strip())

        if symbol != "TRXUSDT":
            return JSONResponse(content={"error": "Unsupported symbol"}, status_code=400)

        last_levels["high"] = high
        last_levels["low"] = low
        print(f"✅ Levels updated: High={high}, Low={low}")

        return {"status": "High/Low levels updated"}

    except Exception as e:
        print("❌ Error:", e)
        return JSONResponse(content={"error": str(e)}, status_code=500)

# === Health check ===
@app.get("/")
def health():
    return {"status": "Bot is online ✅"}
    
