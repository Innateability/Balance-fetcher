from pybit.unified_trading import HTTP
import os

API_KEY = os.getenv("MAIN_API_KEY")
API_SECRET = os.getenv("MAIN_API_SECRET")

session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

symbol = "TRXUSDT"
side = "Buy"
qty = "80"                 # Must be string
entry_price = "0.2778"     # Must be string
trigger_price = "0.278"    # Must be string

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
    position_idx=0
)

print("✅ Order placed!")
print(order)
