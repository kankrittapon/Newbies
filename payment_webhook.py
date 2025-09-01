"""
FastAPI webhook server to auto-approve top-ups from Thai payment gateways.

Supports:
- Opn (Omise) webhook: /webhook/opn
- 2C2P webhook: /webhook/2c2p

This module verifies a shared secret signature (placeholder implementation; replace per provider docs),
extracts TxID from event metadata, and marks the corresponding Google Sheet Topups row as Approved.

Environment variables to set in production:
- OPN_WEBHOOK_SECRET     : bytes-like secret for verifying Opn webhook (HMAC or per their scheme)
- C2P_WEBHOOK_SECRET     : bytes-like secret for verifying 2C2P webhook signature

Run locally for testing:
  uvicorn payment_webhook:app --host 0.0.0.0 --port 8080

Note: Actual signature header names and verification methods differ across providers.
Consult provider docs and swap verify_* implementations accordingly.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os
import hmac
import hashlib
import json
from typing import Any, Dict, Optional

# Local project utils
try:
    from utils import update_topup_status_paid
except Exception:
    # Lazy import fallback will raise clear error at runtime if utils missing
    def update_topup_status_paid(txid: str, amount: Optional[float], provider: str, provider_txn_id: str) -> bool:  # type: ignore
        raise RuntimeError("utils.update_topup_status_paid unavailable")


app = FastAPI(title="Payments Webhook")


def _getenv_bytes(key: str) -> Optional[bytes]:
    v = os.getenv(key)
    return v.encode("utf-8") if v else None


# ---------- Signature helpers (replace with provider-specific verification) ----------
def verify_opn_signature(raw_body: bytes, signature: str | None) -> bool:
    """Example HMAC-SHA256 verification using OPN_WEBHOOK_SECRET.
    Replace with Opn's official signature scheme.
    """
    secret = _getenv_bytes("OPN_WEBHOOK_SECRET")
    if not secret or not signature:
        return False
    mac = hmac.new(secret, msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature)


def verify_2c2p_signature(raw_body: bytes, signature: str | None) -> bool:
    """Example HMAC-SHA256 verification using C2P_WEBHOOK_SECRET.
    Replace with 2C2P canonical verification.
    """
    secret = _getenv_bytes("C2P_WEBHOOK_SECRET")
    if not secret or not signature:
        return False
    mac = hmac.new(secret, msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature)


# ---------- Event parsing helpers ----------
def _extract_fields(evt: Dict[str, Any]) -> Dict[str, Any]:
    """Extract common fields from provider event with multiple fallbacks.
    Returns dict: { txid, amount, currency, provider_txn_id, status }
    """
    # Some providers wrap under {"data": {...}} or {"event": {...}}
    core = evt
    for key in ("data", "event", "payload"):
        if isinstance(core, dict) and isinstance(core.get(key), dict):
            core = core[key]

    def pick(d: Dict[str, Any], *keys):
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None

    meta = core.get("metadata") if isinstance(core.get("metadata"), dict) else {}
    txid = pick(core, "txid", "order_id", "reference_id") or pick(meta, "txid", "order_id")
    amount = pick(core, "amount", "amount_captured", "paid_amount")
    currency = pick(core, "currency", "curr")
    provider_txn_id = pick(core, "id", "charge_id", "transactionId", "invoice_id")
    status = pick(core, "status", "paid_status", "payment_status", "respCode")
    # Normalize amount if nested string
    try:
        amount = float(amount) if amount is not None else None
    except Exception:
        amount = None
    return {
        "txid": txid,
        "amount": amount,
        "currency": currency,
        "provider_txn_id": provider_txn_id,
        "status": status,
    }


def _is_success(provider: str, status: Any) -> bool:
    if status is None:
        return False
    s = str(status).lower()
    if provider == "opn":
        return s in {"successful", "succeeded", "paid", "authorized", "charge.succeeded"}
    if provider == "2c2p":
        # Many 2C2P webhooks carry respCode == "00" for success
        return s in {"success", "paid", "succeeded", "00"}
    return False


# ---------- Webhook endpoints ----------
@app.post("/webhook/opn")
async def webhook_opn(request: Request):
    raw = await request.body()
    sig = request.headers.get("X-Signature") or request.headers.get("X-Opn-Signature")
    if not verify_opn_signature(raw, sig):
        raise HTTPException(status_code=400, detail="invalid signature")

    evt = json.loads(raw.decode("utf-8"))
    fields = _extract_fields(evt)
    if not fields.get("txid"):
        # Ignore if no mapping to our TxID
        return JSONResponse({"ok": True, "ignored": True})

    if _is_success("opn", fields.get("status")):
        ok = update_topup_status_paid(
            txid=str(fields["txid"]),
            amount=fields.get("amount"),
            provider="Opn",
            provider_txn_id=str(fields.get("provider_txn_id") or "")
        )
        if not ok:
            # Could be amount mismatch or TxID not found
            raise HTTPException(status_code=400, detail="update failed")
    return {"ok": True}


@app.post("/webhook/2c2p")
async def webhook_2c2p(request: Request):
    raw = await request.body()
    sig = request.headers.get("X-2C2P-Signature") or request.headers.get("X-Signature")
    if not verify_2c2p_signature(raw, sig):
        raise HTTPException(status_code=400, detail="invalid signature")

    evt = json.loads(raw.decode("utf-8"))
    fields = _extract_fields(evt)
    if not fields.get("txid"):
        return JSONResponse({"ok": True, "ignored": True})

    if _is_success("2c2p", fields.get("status")):
        ok = update_topup_status_paid(
            txid=str(fields["txid"]),
            amount=fields.get("amount"),
            provider="2C2P",
            provider_txn_id=str(fields.get("provider_txn_id") or "")
        )
        if not ok:
            raise HTTPException(status_code=400, detail="update failed")
    return {"ok": True}

