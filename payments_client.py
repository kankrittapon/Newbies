"""
Client-side helper to create payment sessions for QR/e-wallet channels.
This is a placeholder interface that you can wire to Opn/2C2P SDKs or REST.

Usage:
  info = create_payment(txid, amount, channel="promptpay", description="Top-up")
  -> returns {
       "channel": "promptpay|truemoney|linepay",
       "qr_image_url": "..." (if QR),
       "deeplink": "..." (if wallet),
       "expires_at": "ISO8601",
       "provider": "Opn|2C2P",
       "provider_ref": "..."
     }

Replace the stub implementation with real gateway calls; preserve `metadata`/`reference` with the given `txid` so webhook can map back.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Dict, Any


def create_payment(txid: str, amount: float, channel: str, description: str = "Top-up") -> Dict[str, Any]:
    """Create a payment session for a given channel.

    Stub implementation returns a pseudo QR/URL to let UI render something while integrating.
    """
    channel = channel.lower().strip()
    now = datetime.utcnow()
    exp = now + timedelta(minutes=15)

    # STUB ONLY: In production, call Opn/2C2P API to create a charge and return real data.
    # Ensure you send `metadata={"txid": txid}` when creating the charge.
    if channel in ("promptpay", "qr", "promptpay_qr"):
        return {
            "channel": "promptpay",
            "qr_image_url": f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=TXID:{txid}|AMT:{amount}",
            "deeplink": None,
            "expires_at": exp.isoformat(),
            "provider": "Opn",
            "provider_ref": f"stub-{txid}",
        }
    if channel in ("truemoney", "tmn"):
        return {
            "channel": "truemoney",
            "qr_image_url": None,
            "deeplink": f"truemoney://pay?ref={txid}&amount={amount}",
            "expires_at": exp.isoformat(),
            "provider": "Opn",
            "provider_ref": f"stub-{txid}",
        }
    if channel in ("linepay", "line"):
        return {
            "channel": "linepay",
            "qr_image_url": None,
            "deeplink": f"line://pay?ref={txid}&amount={amount}",
            "expires_at": exp.isoformat(),
            "provider": "Opn",
            "provider_ref": f"stub-{txid}",
        }
    # default fallback
    return {
        "channel": channel,
        "qr_image_url": None,
        "deeplink": None,
        "expires_at": exp.isoformat(),
        "provider": "Opn",
        "provider_ref": f"stub-{txid}",
    }

