from datetime import datetime

from backend.models import RentPayment

from tests.conftest import login


def _add_payment(db, lease, owner, amount, paid_at, notes=None):
    payment = RentPayment(
        lease_id=lease.id,
        amount=amount,
        method="CASH",
        receipt_number=RentPayment.generate_receipt_number(),
        paid_at=paid_at,
        recorded_by=owner.id,
        notes=notes,
    )
    db.session.add(payment)
    db.session.commit()
    return payment


def test_owner_can_download_receipt(client, db, owner, active_lease):
    payment = _add_payment(db, active_lease, owner, 500.0, datetime.utcnow())
    login(client, owner.email)
    resp = client.get(f"/rent/payments/{payment.id}/receipt.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert payment.receipt_number in resp.headers["Content-Disposition"]


def test_tenant_can_download_own_receipt(client, db, owner, active_lease):
    payment = _add_payment(db, active_lease, owner, 500.0, datetime.utcnow())
    login(client, active_lease.tenant.user.email)
    resp = client.get(f"/rent/payments/{payment.id}/receipt.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"


def test_tenant_cannot_download_another_tenants_receipt(client, db, owner, active_lease):
    from backend.models import Tenant, User

    payment = _add_payment(db, active_lease, owner, 500.0, datetime.utcnow())
    other_user = User(email="other-receipt@test.com", first_name="Other", last_name="Tenant", role="TENANT")
    other_user.set_password("password123")
    db.session.add(other_user)
    db.session.commit()
    db.session.add(Tenant(user_id=other_user.id, national_id="ID-8888", phone="555-8888"))
    db.session.commit()

    login(client, other_user.email)
    resp = client.get(f"/rent/payments/{payment.id}/receipt.pdf")
    assert resp.status_code == 403


def test_staff_blocked_from_receipt(client, db, owner, staff, active_lease):
    payment = _add_payment(db, active_lease, owner, 500.0, datetime.utcnow())
    login(client, staff.email)
    resp = client.get(f"/rent/payments/{payment.id}/receipt.pdf")
    assert resp.status_code == 403


def test_balance_after_reflects_state_at_time_of_payment(client, db, owner, active_lease):
    # Both payments default to "now" (paid_at=utcnow), so they land on the
    # same calendar day — this specifically exercises the created_at
    # tiebreaker in _balance_after_payment rather than a date boundary.
    balance_before_any_payment = active_lease.balance

    first_payment = RentPayment(
        lease_id=active_lease.id,
        amount=300.0,
        method="CASH",
        receipt_number=RentPayment.generate_receipt_number(),
        recorded_by=owner.id,
    )
    db.session.add(first_payment)
    db.session.commit()

    second_payment = RentPayment(
        lease_id=active_lease.id,
        amount=200.0,
        method="CASH",
        receipt_number=RentPayment.generate_receipt_number(),
        recorded_by=owner.id,
    )
    db.session.add(second_payment)
    db.session.commit()

    from backend.routes.rent import _balance_after_payment

    balance_after_first = _balance_after_payment(active_lease, first_payment)
    balance_after_second = _balance_after_payment(active_lease, second_payment)

    assert balance_after_first == round(balance_before_any_payment - 300.0, 2)
    assert balance_after_second == round(balance_before_any_payment - 500.0, 2)
    assert balance_after_first > balance_after_second


def test_receipt_link_appears_on_statement_page(client, db, owner, active_lease):
    payment = _add_payment(db, active_lease, owner, 500.0, datetime.utcnow())
    login(client, owner.email)
    resp = client.get(f"/rent/{active_lease.id}/statement")
    assert resp.status_code == 200
    assert f"/rent/payments/{payment.id}/receipt.pdf".encode() in resp.data


def test_receipt_link_appears_on_management_history_page(client, db, owner, active_lease):
    payment = _add_payment(db, active_lease, owner, 500.0, datetime.utcnow())
    login(client, owner.email)
    resp = client.get(f"/rent/{active_lease.id}/history")
    assert resp.status_code == 200
    assert f"/rent/payments/{payment.id}/receipt.pdf".encode() in resp.data


def test_receipt_link_appears_on_tenant_portal_history(client, db, owner, active_lease):
    payment = _add_payment(db, active_lease, owner, 500.0, datetime.utcnow())
    login(client, active_lease.tenant.user.email)
    resp = client.get("/portal/history")
    assert resp.status_code == 200
    assert f"/rent/payments/{payment.id}/receipt.pdf".encode() in resp.data
