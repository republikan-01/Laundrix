import hashlib
import hmac
import requests
from flask import current_app

BASE = "https://api.paystack.co"


def _headers():
    key = current_app.config["PAYSTACK_SECRET_KEY"]
    if not key:
        raise RuntimeError("PAYSTACK_SECRET_KEY is not configured.")
    return {"Authorization": f"Bearer {key}"}


def initialize(email, amount_kobo, reference, callback_url):
    r = requests.post(f"{BASE}/transaction/initialize", headers=_headers(), timeout=15, json={
        "email": email, "amount": amount_kobo, "reference": reference,
        "currency": "NGN", "callback_url": callback_url})
    r.raise_for_status()
    body = r.json()
    if not body.get("status"):
        raise RuntimeError(body.get("message", "Paystack refused the request."))
    return body["data"]


def verify(reference):
    r = requests.get(f"{BASE}/transaction/verify/{reference}", headers=_headers(), timeout=15)
    r.raise_for_status()
    body = r.json()
    if not body.get("status"):
        raise RuntimeError(body.get("message", "Verification failed."))
    return body["data"]


def valid_signature(raw_body: bytes, signature: str) -> bool:
    key = current_app.config["PAYSTACK_SECRET_KEY"].encode()
    expected = hmac.new(key, raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature or "")
