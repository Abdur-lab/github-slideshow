from datetime import date, datetime, timedelta

from backend.models import LeaseCharge, RentPayment

from tests.conftest import login


def test_tenant_can_view_own_statement(client, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.get(f"/rent/{active_lease.id}/statement")
    assert resp.status_code == 200
    assert b"Rent Statement" in resp.data


def test_tenant_cannot_view_another_tenants_statement(client, db, active_lease, property_, tenant):
    from backend.models import Tenant, Unit, User

    other_user = User(email="other-tenant@test.com", first_name="Other", last_name="Tenant", role="TENANT")
    other_user.set_password("password123")
    db.session.add(other_user)
    db.session.commit()
    other_tenant = Tenant(user_id=other_user.id, national_id="ID-9999", phone="555-9999")
    db.session.add(other_tenant)
    db.session.commit()

    login(client, other_user.email)
    resp = client.get(f"/rent/{active_lease.id}/statement")
    assert resp.status_code == 403


def test_tenant_statement_hides_management_forms(client, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.get(f"/rent/{active_lease.id}/statement")
    assert resp.status_code == 200
    assert b"Add Charge" not in resp.data
    assert b"Record Reading" not in resp.data
    assert b"Add Revision" not in resp.data


def test_owner_statement_still_shows_management_forms(client, owner, active_lease):
    login(client, owner.email)
    resp = client.get(f"/rent/{active_lease.id}/statement")
    assert resp.status_code == 200
    assert b"Add Charge" in resp.data
    assert b"Record Reading" in resp.data
    assert b"Add Revision" in resp.data


def test_tenant_can_download_own_statement_pdf(client, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.get(f"/rent/{active_lease.id}/statement.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"


def test_staff_blocked_from_statement(client, staff, active_lease):
    login(client, staff.email)
    resp = client.get(f"/rent/{active_lease.id}/statement")
    assert resp.status_code == 403


def test_period_filter_computes_opening_and_closing_balance(client, db, owner, active_lease):
    base = active_lease.start_date
    # A payment before the window (affects opening balance) and one inside it.
    before_payment = RentPayment(
        lease_id=active_lease.id,
        amount=200.0,
        method="CASH",
        receipt_number=RentPayment.generate_receipt_number(),
        paid_at=datetime.combine(base + timedelta(days=1), datetime.min.time()),
        recorded_by=owner.id,
    )
    in_period_payment = RentPayment(
        lease_id=active_lease.id,
        amount=100.0,
        method="CASH",
        receipt_number=RentPayment.generate_receipt_number(),
        paid_at=datetime.combine(base + timedelta(days=10), datetime.min.time()),
        recorded_by=owner.id,
    )
    db.session.add(before_payment)
    db.session.add(in_period_payment)
    db.session.commit()

    period_start = base + timedelta(days=5)
    period_end = base + timedelta(days=20)

    login(client, owner.email)
    resp = client.get(f"/rent/{active_lease.id}/statement?start={period_start.isoformat()}&end={period_end.isoformat()}")
    assert resp.status_code == 200
    # The pre-window payment must not appear as an in-period transaction row,
    # but the in-window one must.
    assert before_payment.receipt_number.encode() not in resp.data
    assert in_period_payment.receipt_number.encode() in resp.data

    expected_opening = round(
        active_lease.total_due_to_date(period_start - timedelta(days=1)) - 200.0, 2
    )
    assert f"{expected_opening:.2f}".encode() in resp.data


def test_invalid_period_falls_back_to_full_statement(client, owner, active_lease):
    login(client, owner.email)
    resp = client.get(f"/rent/{active_lease.id}/statement?start=2030-01-01&end=2020-01-01", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Rent Statement" in resp.data


def test_period_totals_tie_out_to_lease_balance_over_full_history(client, db, owner, active_lease):
    db.session.add(
        LeaseCharge(
            lease_id=active_lease.id,
            charge_type="SUNDRY",
            description="Test sundry",
            amount=33.0,
            recorded_by=owner.id,
        )
    )
    db.session.commit()

    login(client, owner.email)
    start = active_lease.start_date.isoformat()
    end = date.today().isoformat()
    resp = client.get(f"/rent/{active_lease.id}/statement?start={start}&end={end}")
    assert resp.status_code == 200
    assert f"{active_lease.balance:.2f}".encode() in resp.data
