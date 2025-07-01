from pybit.unified_trading import HTTP
import os

# === Bybit API keys ===
API_KEY = os.getenv("MAIN_API_KEY")  # or hardcode: "your_api_key_here"
API_SECRET = os.getenv("MAIN_API_SECRET")

# === Create session ===
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# === Parameters ===
symbol = "TRXUSDT"
side = "Buy"          # or "Sell"
qty = 80             # contracts
entry_price = 0.2778 # the price you want to enter at
trigger_price = 0.278 # trigger price for conditional order

# === Place conditional limit order ===
order = session.place_order(
    category="linear",
    symbol=symbol,
    side=side,
    order_type="Limit",
    qty=qty,
    price=entry_price,
    trigger_price=trigger_price,
    trigger_by="LastPrice",
    time_in_force="GoodTillCancel",
    reduce_only=False,
    close_on_trigger=False,
    position_idx=0  # 0 = default (both sides), 1 = long only, 2 = short only
)

print("✅ Order placed!")
print(order)
