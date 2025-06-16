from fastapi import FastAPI
from pybit.unified_trading import HTTP
import os

app = FastAPI()

# === ENV VARIABLES ===
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

# === BYBIT SESSION ===
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# === ENDPOINT: Fetch Open TRXUSDT Contracts ===
@app.get("/contracts")
def get_open_contracts():
    try:
        symbol = "TRXUSDT"
        category = "linear"
        
        positions = session.get_positions(category=category, symbol=symbol)
        data = positions['result']['list'][0]

        contracts = float(data['size'])  # Size = number of contracts

        return {
            "symbol": symbol,
            "open_contracts": contracts
        }

    except Exception as e:
        return {"error": str(e)
