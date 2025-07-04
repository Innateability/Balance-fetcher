from pybit.unified_trading import HTTP
import os

# === Bybit API keys ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

# === Create Bybit session ===
session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

# === Parameters ===
symbol = "TRXUSDT"
side = "Buy"                # "Buy" or "Sell"
entry_price = 0.2859     # Just for reference — market order executes at current price
tp_price = 0.2861
sl_price = 0.2857
qty = 72                   # Example quantity

# === Place market order with TP and SL in one request ===
try:
    response = session.place_order(
        category="linear",
        symbol=symbol,
        side=side,
        order_type="Market",
        qty=qty,
        take_profit=tp_price,
        stop_loss=sl_price,
        position_idx=0,
        time_in_force="ImmediateOrCancel",
        reduce_only=False,
        close_on_trigger=False
    )

    print("✅ Market order placed with TP and SL!")
    print(response)

except Exception as e:
    print("❌ Error placing order:", e)
    
