from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pybit.unified_trading import HTTP
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import asyncio

app = FastAPI()

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SUB_UID = os.getenv("SUB_UID")

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

signals = {
    "buy": {"entry": None, "high": None, "low": None, "active": False},
    "sell": {"entry": None, "high": None, "low": None, "active": False}
}
monitor_tasks = {}

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

def close_positions(session, label):
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
                print(f"✅ {label}: Closed {side} position with {size} contracts")
    except Exception as e:
        print(f"❌ {label} close failed:", e)

def cancel_all_orders(session):
    try:
        session.cancel_all_orders(category="linear", symbol="TRXUSDT")
        print("❌ All open orders cancelled for TRXUSDT")
    except Exception as e:
        print("⚠️ Failed to cancel orders:", e)

def get_current_price():
    data = main_session.get_tickers(category="linear", symbol="TRXUSDT")
    price = float(data["result"]["list"][0]["lastPrice"])
    return price

async def monitor_price(signal_type):
    global signals

    session = sub_session if signal_type == "buy" else main_session
    label = "Sub" if signal_type == "buy" else "Main"

    entry = signals[signal_type]["entry"]
    high = signals[signal_type]["high"]
    low = signals[signal_type]["low"]

    if not entry or not high or not low:
        print(f"⚠️ Missing entry or high/low for {signal_type.upper()}")
        return

    print(f"👀 Monitoring price for {signal_type.upper()} at {entry}...")

    log_counter = 0

    while True:
        await asyncio.sleep(5)
        price = get_current_price()

        # Print price to logs every 12 * 5sec = 60sec
        log_counter += 1
        if log_counter >= 12:
            print(f"📊 Current price: {price}")
            log_counter = 0

        if (signal_type == "buy" and price >= entry) or (signal_type == "sell" and price <= entry):
            print(f"🚀 Entry price hit for {signal_type.upper()} at {price}")

            sl = low if signal_type == "buy" else high
            rr = abs(entry - sl)
            extra = entry * 0.007
            tp = entry + 1.5 * rr + extra if signal_type == "buy" else entry - 1.5 * rr - extra

            balance = get_usdt_balance(session)
            total = get_usdt_balance(main_session) + get_usdt_balance(sub_session)
            risk = total * 0.10
            sl_diff = abs(entry - sl)
            leverage = 75
            qty_risk = risk / sl_diff
            max_qty = ((balance * leverage) / entry) * 0.9
            qty = max(1, round(min(qty_risk, max_qty)))

            cancel_all_orders(session)
            close_positions(session, label)

            res = session.place_order(
                category="linear",
                symbol="TRXUSDT",
                side="Buy" if signal_type == "buy" else "Sell",
                order_type="Market",
                qty=qty,
                reduce_only=False,
                position_idx=0
            )
            print(f"✅ Market {signal_type.upper()} order placed: {res}")

            while True:
                await asyncio.sleep(5)
                current = get_current_price()

                log_counter += 1
                if log_counter >= 12:
                    print(f"📊 Current price: {current}")
                    log_counter = 0

                if (signal_type == "buy" and (current >= tp or current <= sl)):
                    print(f"🎯 TP or SL hit for {signal_type.upper()} at {current}")
                    close_positions(session, label)
                    rebalance_funds()
                    break
                elif (signal_type == "sell" and (current <= tp or current >= sl)):
                    print(f"🎯 TP or SL hit for {signal_type.upper()} at {current}")
                    close_positions(session, label)
                    rebalance_funds()
                    break

            signals[signal_type]["active"] = False
            signals[signal_type]["entry"] = None
            signals[signal_type]["high"] = None
            signals[signal_type]["low"] = None
            print(f"✅ Trade closed for {signal_type.upper()}, ready for new signals.")
            break

@app.post("/signal")
async def receive_signal(request: Request):
    try:
        body = (await request.body()).decode().strip()
        print("\n📩 Signal received:\n", body)
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        if len(lines) < 2:
            return JSONResponse(content={"error": "Bad format"}, status_code=400)

        symbol = lines[0].upper()
        if symbol != "TRXUSDT":
            return JSONResponse(content={"error": "Unsupported symbol"}, status_code=400)

        signal_type = None
        entry = None
        high = None
        low = None

        for line in lines:
            if "type" in line.lower():
                signal_type = line.split(":")[1].strip().lower()
            elif "entry" in line.lower():
                entry = float(line.split(":")[1].strip())
            elif "high" in line.lower():
                high = float(line.split(":")[1].strip())
            elif "low" in line.lower():
                low = float(line.split(":")[1].strip())

        if entry and signal_type:
            if signal_type not in ["buy", "sell"]:
                return JSONResponse(content={"error": "Invalid type"}, status_code=400)
            if not signals[signal_type]["active"]:
                signals[signal_type]["entry"] = entry
                print(f"✅ Stored new entry for {signal_type.upper()}: {entry}")

                if signal_type not in monitor_tasks or monitor_tasks[signal_type].done():
                    monitor_tasks[signal_type] = asyncio.create_task(monitor_price(signal_type))

                return {"status": f"New entry stored for {signal_type.upper()}"}
            else:
                return {"status": f"Trade already active for {signal_type.upper()}, ignoring entry signal"}

        elif high and low:
            for t in ["buy", "sell"]:
                if not signals[t]["active"]:
                    signals[t]["high"] = high
                    signals[t]["low"] = low
                    print(f"✅ Stored new high/low for {t.upper()}: High={high}, Low={low}")
            return {"status": f"New high/low stored for non-active signals"}

        return JSONResponse(content={"error": "No valid entry or high/low found"}, status_code=400)

    except Exception as e:
        print("❌ Error:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/")
def health():
    return {"status": "Bot is online ✅"}
    
