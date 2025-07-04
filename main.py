from pybit.unified_trading import HTTP
import os

# === Bybit API keys ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

# === YOUR SIGNAL (paste manually here) ===
symbol = "TRXUSDT"
side = "Buy"         # or "Sell"
entry_price = 0.2862
tp_price = 0.2864
sl_price = 0.286
qty = 65            # Your chosen quantity

try:
    # === Decide closing side ===
    close_side = "Sell" if side == "Buy" else "Buy"

    # === Market entry ===
    entry_order = session.place_order(
        category="linear",
        symbol=symbol,
        side=side,
        order_type="Market",
        qty=qty,
        time_in_force="ImmediateOrCancel",
        reduce_only=False,
        position_idx=0
    )
    print("✅ Market order placed:", entry_order)

    # === TP order (limit, reduce-only) ===
    tp_order = session.place_order(
        category="linear",
        symbol=symbol,
        side=close_side,
        order_type="Limit",
        price=tp_price,
        qty=qty,
        reduce_only=True,
        time_in_force="GoodTillCancel",
        position_idx=0
    )
    print("✅ TP order placed at", tp_price)

    # === SL order (limit, reduce-only) ===
    sl_order = session.place_order(
        category="linear",
        symbol=symbol,
        side=close_side,
        order_type="Limit",
        price=sl_price,
        qty=qty,
        reduce_only=True,
        time_in_force="GoodTillCancel",
        position_idx=0
    )
    print("✅ SL order placed at", sl_price)

except Exception as e:
    print("❌ Error:", str(e))

