from fastapi import FastAPI
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

# === Fetch Open Contracts for a Session ===
def fetch_contracts(session, symbol="TRXUSDT", category="linear"):
    try:
        response = session.get_positions(category=category, symbol=symbol)
        positions = response.get("result", {}).get("list", [])
        total_contracts = sum(float(pos["size"]) for pos in positions if pos["symbol"] == symbol)
        return total_contracts
    except Exception as e:
        return f"Error: {str(e)}"

# === Endpoint: GET /contracts ===
@app.get("/contracts")
def get_all_contracts():
    main_contracts = fetch_contracts(main_session)
    sub_contracts = fetch_contracts(sub_session)

    return {
        "symbol": "TRXUSDT",
        "main_account_contracts": main_contracts,
        "sub_account_contracts": sub_contracts
    }
    
