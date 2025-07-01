from pybit.unified_trading import HTTP
import os

# -----------------------------------
# Get parameters from environment
# -----------------------------------
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SUB_UID = os.getenv("SUB_UID")

# -----------------------------------
# Setup Bybit session
# (here using MAIN_API_KEY and MAIN_API_SECRET, but you can switch to sub-account if needed)
# -----------------------------------
session = HTTP(
    testnet=False,    # Set True for testnet
    api_key=MAIN_API_KEY,
    api_secret=MAIN_API_SECRET,
)

# -----------------------------------
# Define order parameters
# -----------------------------------
symbol = "TRXUSDT"
side = "Buy"
order_type = "Limit"           # Order type when triggered
qty = 19
trigger_price = 0.2789
price = 0.27895
order_price_type = "Limit"     # Order type on trigger
position_idx = 1               # 1 = one-way mode, 2 = hedge

# -----------------------------------
# Create conditional order
# -----------------------------------
try:
    response = session.place_order(
        category="linear",           # USDT perpetual
        symbol=symbol,
        side=side,
        order_type=order_type,
        qty=qty,
        price=price,
        trigger_direction=1,        # 1 = trigger above market price, 2 = below
        trigger_price=trigger_price,
        reduce_only=False,
        close_on_trigger=False,
        order_price_type=order_price_type,
        time_in_force="GoodTillCancel",
        position_idx=position_idx,
    )
    print("✅ Order placed successfully:", response)

except Exception as e:
    print("❌ Error placing order:", e)
