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

last_trade = {"type": None, "outcome": None}
trade_log = []

last_levels = {"high": None, "low": None}
active_entry = {"buy": None, "sell": None}

# === Get Balance ===
def get_usdt_balance(session):
    try:
        data = session.get_wallet_balance(accountType="UNIFIED")
        coins = data["result"]["list"][0]["coin"]
        usdt = next((x for x in coins if x["coin"] == "USDT"), None)
        return float(usdt["equity"]) if usdt else 0
    except:
        return 0

# === Rebalance ===
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

# === Close All Positions ===
def close_trades(session, label):
    try:
        pos = session.get_positions(category="linear", symbol="TRXUSDT")["result"]["list"]
        closed = False
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
                print(f"✅ {label} Account: Closed {side} {size}")
                closed = True
        return closed
    except Exception as e:
        print(f"❌ {label} close failed:", e)
        return False

# === Cancel all open orders for TRXUSDT ===
def cancel_all_orders(session):
    try:
        session.cancel_all_orders(category="linear", symbol="TRXUSDT")
        print("❌ All open orders cancelled for TRXUSDT")
    except Exception as e:
        print("⚠️ Failed to cancel orders:", e)

# === Email Summary ===
def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("📧 Email sent")
    except Exception as e:
        print("❌ Email failed:", e)

def summarize_trades():
    if not trade_log:
        return None
    wins = sum(1 for t in trade_log if t["outcome"] == "win")
    losses = sum(1 for t in trade_log if t["outcome"] == "loss")
    return f"WINS: {wins}\nLOSSES: {losses}"

@app.on_event("startup")
async def startup():
    async def summary_loop():
        while True:
            now = datetime.utcnow()
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            await asyncio.sleep((midnight - now).total_seconds())
            summary = summarize_trades()
            if summary:
                send_email("Daily Trade Summary", summary)
                trade_log.clear()
    asyncio.create_task(summary_loop())

# === Signal Receiver ===
@app.post("/signal")
async def receive_signal(request: Request):
    global last_levels, active_entry
    try:
        body = (await request.body()).decode().strip()
        print("\n📩 Signal:\n", body)
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        if len(lines) < 2:
            return JSONResponse(content={"error": "Bad format"}, status_code=400)

        symbol = lines[0].upper()
        signal_type = lines[1].lower()

        if symbol != "TRXUSDT":
            return JSONResponse(content={"error": "Unsupported symbol"}, status_code=400)

        entry = high = low = None
        for line in lines:
            if "entry:" in line.lower():
                entry = float(line.split(":")[1])
            elif "high:" in line.lower():
                high = float(line.split(":")[1])
            elif "low:" in line.lower():
                low = float(line.split(":")[1])

        # High/Low update signal
        if high and low:
            last_levels["high"] = high
            last_levels["low"] = low
            print(f"✅ Updated levels: High={high}, Low={low}")

            # Cancel all open orders on both accounts
            cancel_all_orders(main_session)
            cancel_all_orders(sub_session)

            # Recreate orders if active entry exists
            for side in ["buy", "sell"]:
                if active_entry[side]:
                    await place_order(side, active_entry[side])

            return {"status": "High/Low updated and orders reset"}

        # Entry signal
        elif entry:
            side = "buy" if "buy" in signal_type else "sell"
            active_entry[side] = entry

            # Cancel all open orders on corresponding account
            session = sub_session if side == "buy" else main_session
            cancel_all_orders(session)

            await place_order(side, entry)
            return {"status": f"{side.capitalize()} entry signal received, orders updated"}

        else:
            return JSONResponse(content={"error": "No valid entry or high/low found"}, status_code=400)

    except Exception as e:
        print("❌ Error:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

# === Place Order Helper ===
async def place_order(side, entry):
    global last_levels
    try:
        session = sub_session if side == "buy" else main_session
        label = "Sub" if side == "buy" else "Main"
        high = last_levels["high"]
        low = last_levels["low"]

        if not high or not low:
            print("⚠️ Missing high/low levels, cannot place order")
            return

        sl = low if side == "buy" else high
        rr = abs(entry - sl)
        tp = entry + 1.5 * rr if side == "buy" else entry - 1.5 * rr

        # Check current price
        price = float(session.get_tickers(category="linear", symbol="TRXUSDT")["result"]["list"][0]["lastPrice"])
        immediate_market = (price > entry if side == "buy" else price < entry)

        # Calculate qty
        balance = get_usdt_balance(session)
        total = get_usdt_balance(main_session) + get_usdt_balance(sub_session)
        risk = total * 0.10
        sl_diff = abs(entry - sl)
        leverage = 75
        qty_risk = risk / sl_diff
        max_qty = ((balance * leverage) / entry) * 0.9
        qty = max(1, round(min(qty_risk, max_qty)))

        # Place entry order
        order_type = "Market" if immediate_market else "Limit"
        print(f"Placing {order_type} {side} order at {entry}")

        session.place_order(
            category="linear",
            symbol="TRXUSDT",
            side="Buy" if side == "buy" else "Sell",
            order_type=order_type,
            price=entry if not immediate_market else None,
            qty=qty,
            position_idx=0
        )

        # TP & SL orders
        tick_size = float(session.get_instruments_info(category="linear", symbol="TRXUSDT")['result']['list'][0]['priceFilter']['tickSize'])
        round_price = lambda x: round(round(x / tick_size) * tick_size, 8)
        tp_price = round_price(tp)
        sl_price = round_price(sl)

        for price_level in [tp_price, sl_price]:
            session.place_order(
                category="linear",
                symbol="TRXUSDT",
                side="Sell" if side == "buy" else "Buy",
                order_type="Limit",
                price=price_level,
                qty=qty,
                reduce_only=True,
                time_in_force="GoodTillCancel",
                close_on_trigger=True,
                position_idx=0
            )

        print(f"✅ {side.capitalize()} order placed with TP and SL")
    except Exception as e:
        print(f"❌ Failed to place {side} order:", e)

@app.get("/")
def health():
    return {"status": "Bot is online"}
