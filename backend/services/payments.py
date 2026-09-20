"""Stripe-style online payment handling: dev-mode mock checkout when no API
key is configured, plus manual HMAC webhook verification (independent of the
stripe SDK's own verifier so it can be unit tested fully offline) with
replay protection and idempotent payment recording."""
import hashlib
import hmac
import time

from backend.extensions import db
from backend.models import Lease, RentPayment


def create_checkout_session(lease: Lease, amount: float) -> dict:
    """Returns a dict with a checkout_url. In dev mode (no Stripe key) the
    URL points at our own confirmation route so the flow is testable
    end-to-end without external network access."""
    from flask import current_app, url_for

    api_key = current_app.config.get("STRIPE_SECRET_KEY")
    gateway_ref = f"pi_dev_{lease.id[:8]}_{int(time.time())}"
    if not api_key:
        return {"checkout_url": url_for("portal.pay_confirm", lease_id=lease.id, ref=gateway_ref), "gateway_ref": gateway_ref}

    try:
        import stripe

        stripe.api_key = api_key
        intent = stripe.PaymentIntent.create(amount=int(amount * 100), currency="usd", metadata={"lease_id": lease.id})
        return {"checkout_url": url_for("portal.pay_confirm", lease_id=lease.id, ref=intent.id), "gateway_ref": intent.id}
    except Exception:
        return {"checkout_url": url_for("portal.pay_confirm", lease_id=lease.id, ref=gateway_ref), "gateway_ref": gateway_ref}


def verify_stripe_signature(payload: bytes, sig_header: str, secret: str, tolerance_seconds: int = 300) -> bool:
    """Verifies a 't=<ts>,v1=<hmac>' Stripe-style signature header and
    rejects events older than `tolerance_seconds` (replay protection)."""
    if not sig_header or not secret:
        return False
    try:
        parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    except ValueError:
        return False
    ts, sig = parts.get("t"), parts.get("v1")
    if not ts or not sig:
        return False
    try:
        ts_int = int(ts)
    except ValueError:
        return False
    if abs(time.time() - ts_int) > tolerance_seconds:
        return False
    body = payload.decode() if isinstance(payload, bytes) else payload
    signed_payload = f"{ts}.{body}"
    expected = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def record_idempotent_payment(lease: Lease, amount: float, gateway_ref: str, recorded_by: str, method: str = "ONLINE") -> RentPayment:
    """Duplicate gateway_ref (e.g. a retried webhook) returns the existing
    payment instead of creating a second one."""
    existing = RentPayment.query.filter_by(gateway_ref=gateway_ref).first()
    if existing:
        return existing
    payment = RentPayment(
        lease_id=lease.id,
        amount=amount,
        method=method,
        receipt_number=RentPayment.generate_receipt_number(),
        gateway_ref=gateway_ref,
        recorded_by=recorded_by,
    )
    db.session.add(payment)
    db.session.commit()
    return payment
