from fastapi import FastAPI
import time, hmac, hashlib, requests, uuid, os

# Load Bybit API credentials from environment variables
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
BASE_URL = "https://api.bybit.com"

# Create FastAPI app
app = FastAPI()

def generate_signature(secret: str, params: dict) -> str:
    """Generate Bybit API signature."""
    param_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    return hmac.new(secret.encode("utf-8"), param_str.encode("utf-8"), hashlib.sha256).hexdigest()

@app.get("/transfer")
def transfer_funds():
    """Send 0.1 USDT from Unified account to Fund account."""
    timestamp = str(int(time.time() * 1000))
    transfer_id = f"tr_{timestamp}_{uuid.uuid4().hex[:8]}"

    params = {
        "api_key": API_KEY,
        "timestamp": timestamp,
        "transferId": transfer_id,
        "coin": "USDT",
        "amount": "0.1",
        "fromAccountType": "UNIFIED",
        "toAccountType": "FUND",
    }

    params["sign"] = generate_signature(API_SECRET, params)

    response = requests.post(f"{BASE_URL}/v5/asset/transfer/inter-transfer", data=params)
    return {
        "transferId": transfer_id,
        "status": response.status_code,
        "response": response.json()
  }
