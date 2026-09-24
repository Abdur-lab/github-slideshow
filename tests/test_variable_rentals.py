from datetime import date, timedelta

from backend.models import Lease, RentRevision

from tests.conftest import login


def make_lease(db, unit, tenant, start_date, monthly_rent=1000.0, due_day=1, pro_rata=False):
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=start_date,
        end_date=date(start_date.year + 2, start_date.month, 1),
        monthly_rent=monthly_rent,
        deposit=0,
        due_day=due_day,
        pro_rata=pro_rata,
    )
    db.session.add(lease)
    db.session.commit()
    return lease


def add_revision(db, lease, effective_date, monthly_rent, recorded_by, reason=None):
    revision = RentRevision(
        lease_id=lease.id, effective_date=effective_date, monthly_rent=monthly_rent, reason=reason, recorded_by=recorded_by
    )
    db.session.add(revision)
    db.session.commit()
    return revision


def test_rent_at_defaults_to_base_rent_without_revisions(db, unit, tenant):
    lease = make_lease(db, unit, tenant, date(2024, 1, 1), monthly_rent=1000.0)
    assert lease.rent_at(date(2025, 1, 1)) == 1000.0
    assert lease.current_monthly_rent == 1000.0


def test_rent_at_uses_latest_revision_effective_on_or_before_date(db, unit, tenant, owner):
    lease = make_lease(db, unit, tenant, date(2024, 1, 1), monthly_rent=1000.0)
    add_revision(db, lease, date(2025, 1, 1), 1100.0, owner.id)

    assert lease.rent_at(date(2024, 12, 31)) == 1000.0
    assert lease.rent_at(date(2025, 1, 1)) == 1100.0
    assert lease.rent_at(date(2025, 6, 1)) == 1100.0


def test_rent_at_picks_most_recent_of_multiple_revisions(db, unit, tenant, owner):
    lease = make_lease(db, unit, tenant, date(2024, 1, 1), monthly_rent=1000.0)
    add_revision(db, lease, date(2025, 1, 1), 1100.0, owner.id)
    add_revision(db, lease, date(2026, 1, 1), 1200.0, owner.id)

    assert lease.rent_at(date(2025, 6, 1)) == 1100.0
    assert lease.rent_at(date(2026, 3, 1)) == 1200.0


def test_total_due_to_date_reflects_rent_change_mid_lease(db, unit, tenant, owner):
    lease = make_lease(db, unit, tenant, date(2024, 1, 1), monthly_rent=1000.0, due_day=1)
    add_revision(db, lease, date(2024, 4, 1), 1200.0, owner.id)

    # Feb 1 and Mar 1 due dates are still at the base rate (1000 each);
    # first_due (Jan 1) + Feb 1 + Mar 1 = 3 periods at 1000.
    assert lease.total_due_to_date(date(2024, 3, 1)) == 3000.0
    # Apr 1 onward bills at the revised rate.
    assert lease.total_due_to_date(date(2024, 4, 1)) == 4200.0


def test_current_monthly_rent_property(db, unit, tenant, owner):
    lease = make_lease(db, unit, tenant, date(2024, 1, 1), monthly_rent=1000.0)
    add_revision(db, lease, date(2020, 1, 1), 1200.0, owner.id)
    assert lease.current_monthly_rent == 1200.0
    assert lease.monthly_rent == 1000.0


def test_balance_reflects_rent_revision(db, owner, active_lease):
    balance_before = active_lease.balance
    add_revision(db, active_lease, active_lease.start_date, active_lease.monthly_rent + 500.0, owner.id)
    assert active_lease.balance > balance_before
    assert active_lease.balance == round(active_lease.total_due_to_date() - active_lease.total_paid, 2)


def test_late_fee_uses_revised_rent_for_percentage_type(db, unit, tenant, owner):
    lease = make_lease(db, unit, tenant, date(2024, 1, 1), monthly_rent=1000.0, due_day=1)
    lease.unit.property.late_fee_type = "PERCENTAGE"
    lease.unit.property.late_fee_amount = 10.0
    db.session.commit()
    add_revision(db, lease, date(2024, 2, 1), 2000.0, owner.id)

    # As of Feb 15, the Feb 1 period (billed at the revised 2000 rate) is
    # unpaid and overdue, so the late fee should be 10% of 2000 = 200.
    assert lease.late_fee_due(date(2024, 2, 15)) == 200.0


def test_revise_rent_as_owner(client, db, owner, active_lease):
    login(client, owner.email)
    effective = (active_lease.start_date + timedelta(days=10)).isoformat()
    resp = client.post(
        f"/rent/{active_lease.id}/revise-rent",
        data={"effective_date": effective, "monthly_rent": "1250", "reason": "Annual escalation"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    revisions = RentRevision.query.filter_by(lease_id=active_lease.id).all()
    assert len(revisions) == 1
    assert revisions[0].monthly_rent == 1250.0
    assert revisions[0].reason == "Annual escalation"
    assert b"Annual escalation" in resp.data


def test_revise_rent_requires_positive_amount(client, db, owner, active_lease):
    login(client, owner.email)
    effective = (active_lease.start_date + timedelta(days=10)).isoformat()
    resp = client.post(
        f"/rent/{active_lease.id}/revise-rent",
        data={"effective_date": effective, "monthly_rent": "-5"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert RentRevision.query.filter_by(lease_id=active_lease.id).count() == 0


def test_revise_rent_rejects_date_before_lease_start(client, db, owner, active_lease):
    login(client, owner.email)
    too_early = active_lease.start_date.replace(year=active_lease.start_date.year - 1).isoformat()
    resp = client.post(
        f"/rent/{active_lease.id}/revise-rent",
        data={"effective_date": too_early, "monthly_rent": "1250"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert RentRevision.query.filter_by(lease_id=active_lease.id).count() == 0


def test_revise_rent_blocked_for_tenant(client, active_lease):
    login(client, active_lease.tenant.user.email)
    effective = (active_lease.start_date + timedelta(days=10)).isoformat()
    resp = client.post(
        f"/rent/{active_lease.id}/revise-rent",
        data={"effective_date": effective, "monthly_rent": "1250"},
    )
    assert resp.status_code == 403


def test_revise_rent_blocked_for_staff(client, staff, active_lease):
    login(client, staff.email)
    effective = (active_lease.start_date + timedelta(days=10)).isoformat()
    resp = client.post(
        f"/rent/{active_lease.id}/revise-rent",
        data={"effective_date": effective, "monthly_rent": "1250"},
    )
    assert resp.status_code == 403


def test_statement_page_shows_revisions(client, db, owner, active_lease):
    login(client, owner.email)
    effective = (active_lease.start_date + timedelta(days=10)).isoformat()
    client.post(
        f"/rent/{active_lease.id}/revise-rent",
        data={"effective_date": effective, "monthly_rent": "1250", "reason": "Market adjustment"},
    )
    resp = client.get(f"/rent/{active_lease.id}/statement")
    assert resp.status_code == 200
    assert b"Market adjustment" in resp.data
    assert b"1250.00" in resp.data
