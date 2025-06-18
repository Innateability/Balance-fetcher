from pybit.unified_trading import HTTP
import os

# === API Credentials ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")

# Or just hardcode them here (not recommended for production)
# MAIN_API_KEY = "your_api_key"
# MAIN_API_SECRET = "your_api_secret"

# === Bybit Session ===
main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

# === Close all open positions ===
def close_all_positions():
    try:
        response = main_session.get_positions(category="linear")
        positions = response["result"]["list"]

        for pos in positions:
            symbol = pos["symbol"]
            size = float(pos["size"])
            side = pos["side"]

            if size > 0:
                opposite_side = "Sell" if side == "Buy" else "Buy"
                print(f"📉 Closing {size} contracts on {symbol} with {opposite_side}")

                main_session.place_order(
                    category="linear",
                    symbol=symbol,
                    side=opposite_side,
                    order_type="Market",
                    qty=size,
                    reduce_only=True,
                    position_idx=0
                )

        print("✅ All positions closed")

    except Exception as e:
        print("❌ Failed to close positions:", e)

# === Run it ===
if __name__ == "__main__":
    close_all_positions()
