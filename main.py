from pybit.unified_trading import HTTP
import os

# === Bybit API keys ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

# === YOUR SIGNAL ===
symbol = "TRXUSDT"
side = "Buy"         # or "Sell"
entry_price = 0.2859
tp_price = 0.287
sl_price = 0.284
qty = 57

try:
    # Get tick size
    instruments_info = session.get_instruments_info(category="linear", symbol=symbol)
    tick_size = float(instruments_info["result"]["list"][0]["priceFilter"]["tickSize"])
    round_price = lambda x: round(round(x / tick_size) * tick_size, 8)

    # Round TP & SL prices
    tp_price_rounded = round_price(tp_price)
    sl_price_rounded = round_price(sl_price)

    # Decide closing side
    close_side = "Sell" if side == "Buy" else "Buy"

    # Market entry
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

    # TP order
    tp_order = session.place_order(
        category="linear",
        symbol=symbol,
        side=close_side,
        order_type="Limit",
        price=tp_price_rounded,
        qty=qty,
        reduce_only=True,
        time_in_force="GoodTillCancel",
        position_idx=0
    )
    if tp_order["retCode"] == 0:
        print(f"✅ TP order placed at {tp_price_rounded}")
    else:
        print("❌ TP order error:", tp_order["retMsg"])

    # SL order
    sl_order = session.place_order(
        category="linear",
        symbol=symbol,
        side=close_side,
        order_type="Limit",
        price=sl_price_rounded,
        qty=qty,
        reduce_only=True,
        time_in_force="GoodTillCancel",
        position_idx=0
    )
    if sl_order["retCode"] == 0:
        print(f"✅ SL order placed at {sl_price_rounded}")
    else:
        print("❌ SL order error:", sl_order["retMsg"])

except Exception as e:
    print("❌ Error:", str(e))

