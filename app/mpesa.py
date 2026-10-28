import base64
import os
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

MPESA_ENV = os.getenv("MPESA_ENV", "sandbox")
CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
SHORTCODE = os.getenv("MPESA_SHORTCODE")
PASSKEY = os.getenv("MPESA_PASSKEY")
CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL")

BASE = (
    "https://sandbox.safaricom.co.ke"
    if MPESA_ENV == "sandbox"
    else "https://api.safaricom.co.ke"
)


def get_access_token() -> str:
    url = f"{BASE}/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(url, auth=(CONSUMER_KEY, CONSUMER_SECRET), timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def stk_push(phone: str, amount: int, account_ref: str, description: str) -> dict:
    """
    Sends an STK Push (payment prompt) to the customer's phone.
    Returns the full JSON response from Safaricom.
    """
    token = get_access_token()

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    raw_password = f"{SHORTCODE}{PASSKEY}{timestamp}"
    password = base64.b64encode(raw_password.encode()).decode()

    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": account_ref,
        "TransactionDesc": description,
    }

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{BASE}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers=headers,
        timeout=30,
    )
    return response.json()