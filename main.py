#!/usr/bin/env python3
"""
transfer.py
Send 0.1 USDT from Unified Trading Account -> Funding Account on Bybit.
Generates a unique transferId (CID) automatically.

Usage:
  # set env vars (recommended)
  export BYBIT_API_KEY="your_key"
  export BYBIT_API_SECRET="your_secret"
  python transfer.py

If you must hardcode keys (not recommended), see the HARD_CODED section below.
"""
import os
import time
import uuid
import logging
from pybit.unified_trading import HTTP

# ----- CONFIG -----
AMOUNT = "0.1"
COIN = "USDT"

# Account type ids used by Bybit Unified API (string values)
FROM_ACCOUNT_TYPE = "6"  # Unified Trading
TO_ACCOUNT_TYPE   = "7"  # Funding

# Load API keys from env (recommended)
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
TESTNET = os.getenv("BYBIT_TESTNET", "false").lower() in ("1", "true", "yes")

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("transfer")

# ---- Safety check ----
if not API_KEY or not API_SECRET:
    logger.error("Missing API_KEY or API_SECRET. Set BYBIT_API_KEY and BYBIT_API_SECRET in your environment.")
    raise SystemExit(1)

# --- Create unique transfer id (CID) ---
def make_transfer_id():
    # e.g. tr_1694179200123_a3f4b2c1
    ms = int(time.time() * 1000)
    short = uuid.uuid4().hex[:8]
    return f"tr_{ms}_{short}"

transfer_id = make_transfer_id()
logger.info("Generated transferId (CID) = %s", transfer_id)

# --- Init client ---
session = HTTP(testnet=TESTNET, api_key=API_KEY, api_secret=API_SECRET)

# --- Perform internal transfer ---
def send_unified_to_funding(transfer_id, coin, amount, from_acct, to_acct):
    try:
        resp = session.create_internal_transfer(
            transferId=transfer_id,
            coin=coin,
            amount=amount,
            fromAccountType=from_acct,
            toAccountType=to_acct
        )
        logger.info("Transfer response: %s", resp)
        return resp
    except Exception as e:
        logger.exception("Transfer failed: %s", e)
        raise

if __name__ == "__main__":
    logger.info("Sending %s %s from Unified(%s) -> Funding(%s)", AMOUNT, COIN, FROM_ACCOUNT_TYPE, TO_ACCOUNT_TYPE)
    result = send_unified_to_funding(transfer_id, COIN, AMOUNT, FROM_ACCOUNT_TYPE, TO_ACCOUNT_TYPE)
    logger.info("Done. Check Bybit account history for transferId: %s", transfer_id)
