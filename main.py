from pybit.unified_trading import HTTP
import os

# === ENV ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)

def get_available_usdt(session):
    data = session.get_wallet_balance(accountType="UNIFIED")
    coins = data["result"]["list"][0]["coin"]
    usdt = next((c for c in coins if c["coin"] == "USDT"), None)
    if usdt:
        return float(usdt["availableToWithdraw"])
    return 0

# === Order parameters ===
price = 0.3
qty = 20
leverage = 75

notional = price * qty
initial_margin = notional / leverage

available_usdt = get_available_usdt(main_session)

print(f"💰 Available USDT before placing order: {available_usdt:.6f}")
print(f"📄 Required initial margin: {initial_margin:.6f}")

if available_usdt >= initial_margin:
    try:
        res = main_session.place_order(
            category="linear",
            symbol="TRXUSDT",
            side="Buy",
            order_type="Limit",
            qty=str(qty),
            price=str(price),
            time_in_force="GTC",
            reduce_only=False,
            close_on_trigger=False
        )
        print("✅ Order placed successfully!")
        print(res)
    except Exception as e:
        print("❌ Error placing order:", str(e))
else:
    print("⚠️ Not enough margin to place order.")

# === Fetch updated balance after attempting to place order ===
final_available_usdt = get_available_usdt(main_session)
print(f"💰 Available USDT after operation: {final_available_usdt:.6f}")
