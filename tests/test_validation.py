import io
import time

import pytest
from werkzeug.datastructures import FileStorage

from backend.security import validate, validate_upload
from backend.services.payments import record_idempotent_payment, verify_stripe_signature

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
ZIP_MAGIC = b"PK\x03\x04" + b"\x00" * 20


@pytest.mark.parametrize(
    "value,expected",
    [("10", True), ("0.5", True), ("0", False), ("-3", False), ("abc", False), (None, False)],
)
def test_validate_positive_float(value, expected):
    assert validate("positive_float", value) is expected


@pytest.mark.parametrize("value,expected", [("5", True), ("0", False), ("-1", False), ("x", False)])
def test_validate_positive_int(value, expected):
    assert validate("positive_int", value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [("a@b.com", True), ("a.b+c@example.co.uk", True), ("not-an-email", False), ("", False), (None, False)],
)
def test_validate_email(value, expected):
    assert validate("email", value) is expected


@pytest.mark.parametrize("value,expected", [("2025-06-15", True), ("2025-13-40", False), ("not-a-date", False), (None, False)])
def test_validate_date(value, expected):
    assert validate("date", value) is expected


@pytest.mark.parametrize("value,expected", [("12345678", True), ("short", False), ("", False), (None, False)])
def test_validate_min8(value, expected):
    assert validate("min8", value) is expected


def test_validate_unknown_kind_raises():
    with pytest.raises(ValueError):
        validate("not_a_real_kind", "x")


def test_validate_upload_accepts_real_pdf():
    fs = FileStorage(stream=io.BytesIO(MINIMAL_PDF), filename="lease.pdf")
    assert validate_upload(fs) is True


def test_validate_upload_rejects_zip_renamed_to_pdf():
    fs = FileStorage(stream=io.BytesIO(ZIP_MAGIC), filename="lease.pdf")
    assert validate_upload(fs) is False


def test_validate_upload_rejects_wrong_extension():
    fs = FileStorage(stream=io.BytesIO(MINIMAL_PDF), filename="lease.docx")
    assert validate_upload(fs) is False


def test_validate_upload_rejects_empty_filename():
    fs = FileStorage(stream=io.BytesIO(MINIMAL_PDF), filename="")
    assert validate_upload(fs) is False


def test_validate_upload_rejects_none():
    assert validate_upload(None) is False


def test_stripe_signature_rejects_missing_sig():
    assert verify_stripe_signature(b"{}", "", "secret") is False


def test_stripe_signature_rejects_tampered_payload():
    secret = "whsec_test"
    ts = str(int(time.time()))
    import hashlib
    import hmac

    good_sig = hmac.new(secret.encode(), f"{ts}.{{}}".encode(), hashlib.sha256).hexdigest()
    header = f"t={ts},v1={good_sig}"
    assert verify_stripe_signature(b'{"tampered": true}', header, secret) is False


def test_stripe_signature_accepts_valid_recent_signature():
    secret = "whsec_test"
    ts = str(int(time.time()))
    payload = b'{"type": "payment_intent.succeeded"}'
    import hashlib
    import hmac

    sig = hmac.new(secret.encode(), f"{ts}.{payload.decode()}".encode(), hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"
    assert verify_stripe_signature(payload, header, secret) is True


def test_stripe_signature_rejects_old_timestamp():
    secret = "whsec_test"
    old_ts = str(int(time.time()) - 301)
    payload = b'{"type": "payment_intent.succeeded"}'
    import hashlib
    import hmac

    sig = hmac.new(secret.encode(), f"{old_ts}.{payload.decode()}".encode(), hashlib.sha256).hexdigest()
    header = f"t={old_ts},v1={sig}"
    assert verify_stripe_signature(payload, header, secret) is False


def test_idempotent_payment_duplicate_gateway_ref_creates_one_payment(db, active_lease, manager):
    from backend.models import RentPayment

    p1 = record_idempotent_payment(active_lease, 500.0, "pi_test_123", manager.id)
    p2 = record_idempotent_payment(active_lease, 500.0, "pi_test_123", manager.id)
    assert p1.id == p2.id
    assert RentPayment.query.filter_by(gateway_ref="pi_test_123").count() == 1


def test_sendgrid_dispatch_marks_sent_when_no_provider(app, db, owner):
    from backend.services.notifications import send_email

    with app.app_context():
        notif = send_email(owner, "Test subject", "Test body")
        assert notif.status == "SENT"


def test_sendgrid_dispatch_marks_failed_on_api_error(app, db, owner, monkeypatch):
    import sendgrid

    from backend.services.notifications import send_email

    class BoomClient:
        def __init__(self, api_key):
            raise RuntimeError("simulated provider outage")

    monkeypatch.setattr(sendgrid, "SendGridAPIClient", BoomClient)
    with app.app_context():
        app.config["SENDGRID_API_KEY"] = "fake-key-for-test"
        notif = send_email(owner, "Test subject", "Test body")
        assert notif.status == "FAILED"
        assert notif.retry_count == 1
