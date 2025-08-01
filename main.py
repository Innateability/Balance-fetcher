from fastapi import FastAPI, Request
import requests
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

@app.get("/")
def root():
    return {"message": "Service is alive"}

@app.api_route("/ping", methods=["GET", "HEAD"])
async def ping(request: Request):
    symbol = "TRXUSDT"
    interval = "5"
    limit = 1

    url = "https://api.bybit.com/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if data.get("retCode") != 0:
            logging.error(f"Bybit API error: {data}")
            return {"error": "Failed to fetch kline data"}

        kline = data["result"]["list"][0]
        open_price = kline[1]
        high_price = kline[2]
        low_price = kline[3]
        close_price = kline[4]

        logging.info(f"{symbol} (5m) - Open: {open_price}, High: {high_price}, Low: {low_price}, Close: {close_price}")

        if request.method == "HEAD":
            return {}

        return {
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price
        }

    except Exception as e:
        logging.error(f"Exception: {e}")
        return {"error": str(e)}
