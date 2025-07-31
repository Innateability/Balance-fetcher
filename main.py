from fastapi import FastAPI
import requests
import logging

app = FastAPI()

# Set up basic logging
logging.basicConfig(level=logging.INFO)

@app.get("/ping")
async def handle_ping():
    symbol = "TRXUSDT"
    interval = "5"
    limit = 1

    url = f"https://api.bybit.com/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if data["retCode"] != 0:
            logging.error(f"Bybit API error: {data}")
            return {"error": "Failed to fetch kline data"}

        kline = data["result"]["list"][0]
        open_price = kline[1]
        high_price = kline[2]
        low_price = kline[3]
        close_price = kline[4]

        logging.info(f"{symbol} (5m) - Open: {open_price}, High: {high_price}, Low: {low_price}, Close: {close_price}")

        return {"status": "ok"}

    except Exception as e:
        logging.error(f"Exception: {e}")
        return {"error": str(e)}
