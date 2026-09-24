import io
from datetime import date

from backend.models import Lease

from tests.conftest import login


def make_lease(db, unit, tenant, start_date, monthly_rent=1000.0, due_day=1, pro_rata=False):
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=start_date,
        end_date=date(start_date.year + 1, start_date.month, 1),
        monthly_rent=monthly_rent,
        deposit=0,
        due_day=due_day,
        pro_rata=pro_rata,
    )
    db.session.add(lease)
    db.session.commit()
    return lease


def test_first_period_amount_mid_month(db, unit, tenant):
    lease = make_lease(db, unit, tenant, date(2024, 1, 15), monthly_rent=1000.0)
    # January has 31 days; days occupied = 31 - 15 + 1 = 17
    assert lease.first_period_amount() == round(1000.0 / 31 * 17, 2)


def test_first_period_amount_full_when_starting_on_first(db, unit, tenant):
    lease = make_lease(db, unit, tenant, date(2024, 3, 1), monthly_rent=1000.0)
    assert lease.first_period_amount() == 1000.0


def test_total_due_uses_prorated_first_period_when_enabled(db, unit, tenant):
    lease = make_lease(db, unit, tenant, date(2024, 1, 15), monthly_rent=1000.0, due_day=1, pro_rata=True)
    # First due date is Feb 1 (due_day=1, clipped so candidate Jan 1 < start -> next month)
    as_of = lease.first_due_date()
    assert lease.total_due_to_date(as_of) == lease.first_period_amount()
    assert lease.total_due_to_date(as_of) < lease.monthly_rent


def test_total_due_unaffected_when_pro_rata_disabled(db, unit, tenant):
    lease = make_lease(db, unit, tenant, date(2024, 1, 15), monthly_rent=1000.0, due_day=1, pro_rata=False)
    as_of = lease.first_due_date()
    assert lease.total_due_to_date(as_of) == lease.monthly_rent


def test_subsequent_periods_charged_in_full_with_pro_rata(db, unit, tenant):
    lease = make_lease(db, unit, tenant, date(2024, 1, 15), monthly_rent=1000.0, due_day=1, pro_rata=True)
    first_due = lease.first_due_date()
    second_due = lease._advance_month(first_due)
    expected = round(lease.first_period_amount() + lease.monthly_rent, 2)
    assert lease.total_due_to_date(second_due) == expected


def test_balance_reflects_proration(db, unit, tenant):
    prorated = make_lease(db, unit, tenant, date(2024, 1, 15), monthly_rent=1000.0, due_day=1, pro_rata=True)
    full = make_lease(db, unit, tenant, date(2024, 1, 15), monthly_rent=1000.0, due_day=1, pro_rata=False)
    as_of = prorated.first_due_date()
    assert prorated.total_due_to_date(as_of) < full.total_due_to_date(as_of)
    assert full.total_due_to_date(as_of) == full.monthly_rent


def test_upload_lease_saves_pro_rata_flag(client, db, owner, tenant, unit):
    login(client, owner.email)
    resp = client.post(
        f"/tenants/{tenant.id}/upload-lease",
        data={
            "unit_id": unit.id,
            "start_date": "2024-01-15",
            "end_date": "2025-01-15",
            "monthly_rent": "1000",
            "deposit": "0",
            "due_day": "1",
            "pro_rata": "on",
            "lease_document": (io.BytesIO(b"%PDF-1.4 fake"), "lease.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    lease = Lease.query.filter_by(unit_id=unit.id, tenant_id=tenant.id).first()
    assert lease is not None
    assert lease.pro_rata is True


def test_upload_lease_defaults_pro_rata_false(client, db, owner, tenant, unit):
    login(client, owner.email)
    resp = client.post(
        f"/tenants/{tenant.id}/upload-lease",
        data={
            "unit_id": unit.id,
            "start_date": "2024-01-15",
            "end_date": "2025-01-15",
            "monthly_rent": "1000",
            "deposit": "0",
            "due_day": "1",
            "lease_document": (io.BytesIO(b"%PDF-1.4 fake"), "lease.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    lease = Lease.query.filter_by(unit_id=unit.id, tenant_id=tenant.id).first()
    assert lease is not None
    assert lease.pro_rata is False


def test_statement_page_shows_proration_note(client, db, owner, unit, tenant):
    lease = make_lease(db, unit, tenant, date(2024, 1, 15), monthly_rent=1000.0, due_day=1, pro_rata=True)
    login(client, owner.email)
    resp = client.get(f"/rent/{lease.id}/statement")
    assert resp.status_code == 200
    assert b"Pro rata" in resp.data
