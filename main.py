from pybit.unified_trading import HTTP
import os

# ------------------------------
# Setup your Bybit API keys
# ------------------------------
api_key = "MAIN_API_KEY"
api_secret = "MAIN_API_SECRET"

# ------------------------------
# Create Bybit HTTP session
# ------------------------------
session = HTTP(
    testnet=False,    # Set to True if you're using testnet
    api_key=api_key,
    api_secret=api_secret,
)

# ------------------------------
# Define parameters
# ------------------------------
symbol = "TRXUSDT"
side = "Buy"
order_type = "Limit"           # The order that gets placed when condition is met
trigger_price = 0.2789
qty = 19
price = 0.27895                # Entry price once triggered
order_price_type = "Limit"     # The order type when condition triggers (Limit or Market)
position_idx = 1               # 1 for one-way mode

# Optional: Take profit and stop loss examples (set or leave out if not needed)
take_profit = {
    "trigger_price": 0.2800,
    "order_price_type": "Market",
    "price": 0.2800
}
stop_loss = {
    "trigger_price": 0.2770,
    "order_price_type": "Market",
    "price": 0.2770
}

# ------------------------------
# Create conditional order
# ------------------------------
try:
    response = session.place_order(
        category="linear",         # USDT perpetual
        symbol=symbol,
        side=side,
        order_type="Limit",
        qty=qty,
        price=price,
        trigger_direction=1,      # 1 = trigger above market price, 2 = below
        trigger_price=trigger_price,
        reduce_only=False,
        close_on_trigger=False,
        order_price_type=order_price_type,
        time_in_force="GoodTillCancel",
        position_idx=position_idx,
        take_profit=take_profit["price"],
        stop_loss=stop_loss["price"],
        tp_trigger_by="LastPrice",
        sl_trigger_by="LastPrice"
    )
    print("✅ Order placed successfully:", response)

except Exception as e:
    print("❌ Error placing order:", e)
    
