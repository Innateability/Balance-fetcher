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

trade_log = []

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

def close_trades(session, label):
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
                print(f"✅ {label} Account: Closed {side} {size}")
        return True
    except Exception as e:
        print(f"❌ {label} close failed:", e)
        return False

def cancel_all_orders(session):
    try:
        session.cancel_all_orders(category="linear", symbol="TRXUSDT")
        print("❌ All open orders cancelled for TRXUSDT")
    except Exception as e:
        print("⚠️ Failed to cancel orders:", e)

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

@app.post("/signal")
async def receive_signal(request: Request):
    try:
        body = (await request.body()).decode().strip()
        print("\n📩 Signal:\n", body)
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        if len(lines) < 4:
            return JSONResponse(content={"error": "Bad format"}, status_code=400)

        symbol = lines[0].upper()
        signal_type = lines[1].split(":")[1].strip().lower()
        entry = float(lines[2].split(":")[1].strip())
        tp = float(lines[3].split(":")[1].strip())
        sl = float(lines[4].split(":")[1].strip())

        if symbol != "TRXUSDT":
            return JSONResponse(content={"error": "Unsupported symbol"}, status_code=400)

        side = "buy" if signal_type == "buy" else "sell"
        session = sub_session if side == "buy" else main_session

        # Cancel all orders before new trade
        cancel_all_orders(session)

        # Close any open positions before new trade
        close_trades(session, "Main" if side == "sell" else "Sub")

        # Calculate qty
        balance = get_usdt_balance(session)
        total = get_usdt_balance(main_session) + get_usdt_balance(sub_session)
        risk = total * 0.10
        sl_diff = abs(entry - sl)
        leverage = 75
        qty_risk = risk / sl_diff
        max_qty = ((balance * leverage) / entry) * 0.9
        qty = max(1, round(min(qty_risk, max_qty)))

        # Place market order
        print(f"📥 Placing Market {side} order at ~{entry} with qty={qty}")

        session.place_order(
            category="linear",
            symbol="TRXUSDT",
            side="Buy" if side == "buy" else "Sell",
            order_type="Market",
            qty=qty,
            reduce_only=False,
            position_idx=0
        )

        # TP & SL reduce-only orders
        for target_price in [tp, sl]:
            session.place_order(
                category="linear",
                symbol="TRXUSDT",
                side="Sell" if side == "buy" else "Buy",
                order_type="Limit",
                price=target_price,
                qty=qty,
                reduce_only=True,
                time_in_force="GoodTillCancel",
                close_on_trigger=True,
                position_idx=0
            )
        print(f"✅ {side.capitalize()} order with TP and SL placed.")

        return {"status": f"{side.capitalize()} market order placed with TP and SL"}

    except Exception as e:
        print("❌ Error:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/")
def health():
    return {"status": "Bot is online ✅"}
    
