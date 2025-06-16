from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
import os

app = FastAPI()

# === ENV VARIABLES ===
MAIN_API_KEY = os.getenv("MAIN_API_KEY")
MAIN_API_SECRET = os.getenv("MAIN_API_SECRET")
SUB_API_KEY = os.getenv("SUB_API_KEY")
SUB_API_SECRET = os.getenv("SUB_API_SECRET")

# === BYBIT SESSIONS ===
main_session = HTTP(api_key=MAIN_API_KEY, api_secret=MAIN_API_SECRET)
sub_session = HTTP(api_key=SUB_API_KEY, api_secret=SUB_API_SECRET)

# === Store for pending signals ===
stored_signals = {
    "buy": [],
    "sell": []
}

# === Utility ===
def fuzzy_match(val1, val2, tolerance=1e-5):
    return abs(val1 - val2) <= tolerance

def round_sf(val, sf=4):
    if val == 0:
        return 0
    from math import log10, floor
    return round(val, sf - int(floor(log10(abs(val)))) - 1)

# === Fetch contract size ===
def get_open_contracts(session):
    try:
        response = session.get_positions(category="linear", symbol="TRXUSDT")
        return float(response["result"]["list"][0]["size"])
    except:
        return 0.0

# === Place reverse trade ===
def place_opposite_trade(session, symbol, qty, direction):
    side = "Buy" if direction == "buy" else "Sell"
    try:
        session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            reduce_only=False,
            position_idx=0
        )
        return True
    except Exception as e:
        print("❌ Trade failed:", str(e))
        return False

# === POST /signal ===
@app.post("/signal")
async def receive_signal(request: Request):
    try:
        message = (await request.body()).decode()
        print("\n📩 Received Signal:\n", message)

        lines = message.strip().splitlines()
        if not lines or len(lines) < 2:
            return {"error": "Invalid signal format"}

        symbol = lines[0].strip().upper()
        data = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip().lower()] = value.strip()

        signal_type = data.get("type", "").lower()
        if signal_type not in ["buy", "sell"]:
            return {"error": "Invalid type"}

        tp = round_sf(float(data.get("tp", 0)))
        sl = round_sf(float(data.get("sl", 0)))
        entry = data.get("entry")

        # Signal with entry — store it
        if entry:
            entry = round_sf(float(entry))
            stored_signals[signal_type].append({
                "symbol": symbol,
                "type": signal_type,
                "entry": entry,
                "tp": tp,
                "sl": sl
            })
            return {"status": f"{signal_type} signal stored"}

        # Signal without entry — try to match
        for s in stored_signals[signal_type]:
            if fuzzy_match(tp, s["tp"]) and fuzzy_match(sl, s["sl"]):
                # Found a fuzzy match
                session = main_session if signal_type == "sell" else sub_session
                contracts = get_open_contracts(session)

                if contracts <= 0:
                    return {"status": "No contracts to reverse"}

                opposite_type = "buy" if signal_type == "sell" else "sell"
                placed = place_opposite_trade(session, symbol, contracts, opposite_type)

                if placed:
                    stored_signals[signal_type].remove(s)
                    return {
                        "status": "Opposite trade executed",
                        "direction": opposite_type,
                        "contracts": contracts,
                        "matched_entry": s["entry"]
                    }
                else:
                    return {"error": "Failed to place reverse trade"}

        return {"status": "No matching signal found"}

    except Exception as e:
        return {"error": str(e)}        

# === Health Check ===
@app.get("/")
def root():
    return {"status": "Bot is online"}
    
