from pybit.unified_trading import HTTP
import os

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

# === Your trade parameters ===
symbol = "TRXUSDT"
side = "Buy"  # or "Sell"
entry = 0.27611
tp = 0.2779730550000001
sl = 0.27496

# === Cancel all open orders first ===
def cancel_all_orders(session):
    try:
        session.cancel_all_orders(category="linear", symbol=symbol)
        print("✅ All open orders cancelled")
    except Exception as e:
        print("⚠️ Cancel orders failed:", e)

# === Get USDT balance ===
def get_usdt_balance(session):
    try:
        data = session.get_wallet_balance(accountType="UNIFIED")
        coins = data["result"]["list"][0]["coin"]
        usdt = next((x for x in coins if x["coin"] == "USDT"), None)
        return float(usdt["equity"]) if usdt else 0
    except:
        return 0

# === Place order ===
def place_main_order():
    try:
        session = main_session

        cancel_all_orders(session)

        # Get current price
        price = float(session.get_tickers(category="linear", symbol=symbol)["result"]["list"][0]["lastPrice"])
        immediate_market = (price > entry if side == "Buy" else price < entry)

        # Calculate qty
        balance = get_usdt_balance(session)
        risk_amount = balance * 0.10
        sl_diff = abs(entry - sl)
        leverage = 75
        qty_risk = risk_amount / sl_diff
        max_qty = ((balance * leverage) / entry) * 0.9
        qty = max(1, round(min(qty_risk, max_qty)))

        print(f"📢 Placing {side} market order at {entry}, qty={qty}")

        # Entry order
        res = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            reduce_only=False,
            close_on_trigger=False,
            position_idx=0,
            time_in_force="ImmediateOrCancel"
        )
        print("✅ Entry order placed:", res)

        # Get tick size
        tick_size = float(session.get_instruments_info(category="linear", symbol=symbol)['result']['list'][0]['priceFilter']['tickSize'])
        round_price = lambda x: round(round(x / tick_size) * tick_size, 8)

        tp_price = round_price(tp)
        sl_price = round_price(sl)

        # TP order
        session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            order_type="Limit",
            price=tp_price,
            qty=qty,
            reduce_only=True,
            time_in_force="GoodTillCancel",
            close_on_trigger=True,
            position_idx=0
        )
        print(f"✅ TP order placed at {tp_price}")

        # SL order
        session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            order_type="Limit",
            price=sl_price,
            qty=qty,
            reduce_only=True,
            time_in_force="GoodTillCancel",
            close_on_trigger=True,
            position_idx=0
        )
        print(f"✅ SL order placed at {sl_price}")

        print("🎉 Done.")

    except Exception as e:
        print("❌ Failed to place order:", e)

# === Run immediately ===
if __name__ == "__main__":
    place_main_order()
    
