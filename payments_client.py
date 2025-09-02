# payments_client.py
"""
Client-side helper to create payment sessions for QR/e-wallet channels.
Drop-in replacement: preserves original return keys exactly.

Updates:
- Canonicalize channel names: promptpay | truemoney | linepay
- Validate amount: 2 decimals + allowlist (e.g. 1500/2500/3500) via env
- Proper ISO8601 with timezone (UTC)
- Stripe-only (removed OPN/2C2P)
- Stable, non-guessable provider_ref
- Calls Payment Backend (/api/stripe/create-checkout-session)
- Propagate username (optional) and client_txid (optional)
"""

from __future__ import annotations

import os
import uuid
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Set

# ---------- Config (env) ----------

def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default

def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default

def _parse_amount_set(s: str) -> Set[float]:
    out: Set[float] = set()
    for part in (s or "").split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(round(float(p), 2))
        except Exception:
            pass
    return out

# ช่วงจำนวนเงินกว้าง (กันกรณี env ไม่ตั้งค่า)
MIN_TOPUP_THB = _float_env("MIN_TOPUP_THB", 20.0)         # ขั้นต่ำ
MAX_TOPUP_THB = _float_env("MAX_TOPUP_THB", 50000.0)      # สูงสุด
QR_EXPIRE_MIN = _int_env("QR_EXPIRE_MIN", 15)             # นาทีหมดอายุที่ UI แสดง

# Allowlist สำหรับ map role, ตั้งผ่าน ENV ได้ เช่น: ALLOWED_AMOUNTS="1500,2500,3500"
ALLOWED_AMOUNTS = _parse_amount_set(os.getenv("ALLOWED_AMOUNTS", "1500,2500,3500"))

# Tier mapping (VIP -> THB) for convenience in the app UI
ROLE_BY_AMOUNT: Dict[float, str] = {
    1500.0: "VIPI",
    2500.0: "VIPII",
    3500.0: "VIPIII",
}
AMOUNT_BY_TIER: Dict[str, float] = {v: k for k, v in ROLE_BY_AMOUNT.items()}

PAYMENT_BACKEND_BASE = os.getenv(
    "PAYMENT_BACKEND_BASE",
    "https://payments-worker.bokkchoypayment.workers.dev",
).rstrip("/")

CURRENCY = os.getenv("TOPUP_CURRENCY", "thb").lower()

# OPTIONAL: หากโปรแกรมหลัก set ชื่อผู้ใช้ไว้ที่ env
CURRENT_USERNAME = os.getenv("CURRENT_USERNAME")  # ถ้าไม่มี ให้ส่งเป็น "-" แทน
CURRENT_ROLE = os.getenv("CURRENT_ROLE")

def _is_admin(role: Optional[str]) -> bool:
    r = (role or CURRENT_ROLE or "").strip().lower()
    return r == "admin"

# ---------- Helpers ----------

def _canonical_channel(ch: str) -> str:
    c = (ch or "").strip().lower()
    if c in ("promptpay", "qr", "promptpay_qr"):
        return "promptpay"
    if c in ("truemoney", "tmn"):
        return "truemoney"
    if c in ("linepay", "line"):
        return "linepay"
    return c

def _validate_amount(amount: float) -> None:
    # 2 ตำแหน่งทศนิยม
    if round(amount, 2) != float(f"{amount:.2f}"):
        raise ValueError("amount must have at most 2 decimal places")

    # อยู่ในช่วงกว้าง (กันค่าผิดปกติ)
    if not (MIN_TOPUP_THB <= amount <= MAX_TOPUP_THB):
        raise ValueError(
            f"amount out of bounds: {amount} (allowed {MIN_TOPUP_THB}-{MAX_TOPUP_THB} THB)"
        )

    # ถ้าเซ็ต allowlist (เช่น 1500/2500/3500) ต้องตรงเป๊ะ
    if ALLOWED_AMOUNTS and round(amount, 2) not in ALLOWED_AMOUNTS:
        allowed_str = ", ".join(str(int(a)) if a.is_integer() else str(a) for a in sorted(ALLOWED_AMOUNTS))
        raise ValueError(f"amount must be one of {{{allowed_str}}}")

def _expires_at_iso(minutes: int = QR_EXPIRE_MIN) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()

def _mk_ref(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"

# ---------- Internal call to Payment Backend ----------

def _create_checkout_session(
    amount_baht: float,
    description: str,
    username: Optional[str] = None,
    client_txid: Optional[str] = None,
) -> dict:
    """
    เรียก Payment Backend เพื่อสร้าง Stripe Checkout Session
    คืน {"sessionId": "...", "txid": "...", "url": "..."} (หาก backend ส่ง txid กลับมา)
    """
    payload = {
        "amount": int(round(amount_baht * 100)),  # minor units
        "currency": CURRENCY,
        "description": description,
        # ช่องทางส่งข้อมูลเสริมให้ backend ผูกกับ TxID/metadata
        "username": (username or CURRENT_USERNAME or "-"),
        "client_txid": client_txid or None,  # เผื่อ backend รองรับ; ถ้าไม่รองรับจะถูกมองข้าม
    }
    # ลบ key ที่เป็น None เพื่อความสะอาด
    payload = {k: v for k, v in payload.items() if v is not None}

    url = f"{PAYMENT_BACKEND_BASE}/api/stripe/create-checkout-session"
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

# ---------- Public API ----------

def create_payment_by_tier(
    tier: str,
    username: Optional[str] = None,
    client_txid: Optional[str] = None,
    role: Optional[str] = None,
    channel: str = "promptpay",
) -> Dict[str, Any]:
    """
    Convenience wrapper: choose a tier (VIPI/VIPII/VIPIII) and create a Stripe Checkout session.
    Returns the same shape as create_payment. Raises ValueError if tier is invalid.
    """
    t = (tier or "").strip().upper()
    if t not in AMOUNT_BY_TIER:
        raise ValueError(f"invalid tier: {tier} (allowed: {', '.join(AMOUNT_BY_TIER.keys())})")
    amount = AMOUNT_BY_TIER[t]
    return create_payment(
        txid=client_txid or "",
        amount=amount,
        channel=channel,
        description=f"Top-up {t}",
        username=username,
        role=role,
    )


def create_payment(
    txid: str,
    amount: float,
    channel: str,
    description: str = "Top-up",
    username: Optional[str] = None,
    role: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a payment session for a given channel.

    Returns keys exactly as original: channel, qr_image_url, deeplink, expires_at, provider, provider_ref

    Notes:
    - txid parameter kept for compatibility; actual TxID is generated/tracked by Payment Backend.
    - You can pass username here (or via env CURRENT_USERNAME) so the backend knows whose top-up it is.
    """
    channel = _canonical_channel(channel)
    amount = round(float(amount), 2)
    if _is_admin(role):
        if round(amount, 2) != float(f"{amount:.2f}") or amount <= 0:
            raise ValueError("amount must be > 0 and have at most 2 decimal places")
    else:
        _validate_amount(amount)

    # ใช้ txid ฝั่ง client เป็น client_txid (ถ้า backend รองรับก็จะผูกให้)
    sess = _create_checkout_session(
        amount_baht=amount,
        description=f"{description} ({channel})",
        username=username,
        client_txid=txid or None,
    )
    session_id = str(sess.get("sessionId") or "")
    checkout_url = str(sess.get("url") or "")

    return {
        "channel": channel,
        "qr_image_url": None,                 # ให้ผู้ใช้ไปชำระใน Checkout URL
        "deeplink": checkout_url,             # Stripe Checkout ใช้แทน deeplink
        "expires_at": _expires_at_iso(QR_EXPIRE_MIN),
        "provider": "Stripe",
        "provider_ref": session_id,           # session id จาก Stripe (ไว้ debug / อ้างอิง)
    }
