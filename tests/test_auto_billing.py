from datetime import date, timedelta

from backend.models import Lease, Notification, RentInvoice, RentRevision
from backend.scheduler_jobs import ALL_JOBS, job_auto_bill_rent

from tests.conftest import login


def _make_lease(db, unit, tenant, start_offset_days, due_day=1, pro_rata=False):
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=date.today() + timedelta(days=start_offset_days),
        end_date=date.today() + timedelta(days=365),
        monthly_rent=unit.monthly_rent,
        deposit=unit.deposit,
        due_day=due_day,
        pro_rata=pro_rata,
    )
    db.session.add(lease)
    db.session.commit()
    return lease


def test_bills_one_invoice_per_elapsed_period(app, db, unit, tenant):
    with app.app_context():
        lease = _make_lease(db, unit, tenant, start_offset_days=-200)
        expected_dates = lease.due_dates_to_date(date.today())
        assert len(expected_dates) >= 1

        sent = job_auto_bill_rent()

        assert sent == len(expected_dates)
        invoices = RentInvoice.query.filter_by(lease_id=lease.id).all()
        assert len(invoices) == len(expected_dates)
        assert {inv.period_due_date for inv in invoices} == set(expected_dates)
        for inv in invoices:
            assert inv.amount == lease.amount_for_period(inv.period_due_date)


def test_job_is_idempotent(app, db, unit, tenant):
    with app.app_context():
        lease = _make_lease(db, unit, tenant, start_offset_days=-200)
        first_run = job_auto_bill_rent()
        assert first_run >= 1
        second_run = job_auto_bill_rent()
        assert second_run == 0
        assert RentInvoice.query.filter_by(lease_id=lease.id).count() == first_run


def test_skips_leases_before_first_due_date(app, db, unit, tenant):
    with app.app_context():
        lease = _make_lease(db, unit, tenant, start_offset_days=200)
        sent = job_auto_bill_rent()
        assert sent == 0
        assert RentInvoice.query.filter_by(lease_id=lease.id).count() == 0


def test_skips_non_active_leases(app, db, unit, tenant):
    with app.app_context():
        lease = _make_lease(db, unit, tenant, start_offset_days=-200)
        lease.status = "TERMINATED"
        db.session.commit()
        sent = job_auto_bill_rent()
        assert sent == 0


def test_first_period_invoice_reflects_pro_rata(app, db, unit, tenant):
    with app.app_context():
        lease = _make_lease(db, unit, tenant, start_offset_days=-200, pro_rata=True)
        job_auto_bill_rent()
        first_due = lease.first_due_date()
        first_invoice = RentInvoice.query.filter_by(lease_id=lease.id, period_due_date=first_due).first()
        assert first_invoice is not None
        assert first_invoice.amount == lease.first_period_amount()
        assert first_invoice.amount < lease.monthly_rent


def test_invoice_amounts_reflect_rent_revision(app, db, unit, tenant, owner):
    with app.app_context():
        lease = _make_lease(db, unit, tenant, start_offset_days=-200)
        due_dates = lease.due_dates_to_date(date.today())
        assert len(due_dates) >= 2
        midpoint = due_dates[len(due_dates) // 2]
        db.session.add(
            RentRevision(lease_id=lease.id, effective_date=midpoint, monthly_rent=lease.monthly_rent + 250, recorded_by=owner.id)
        )
        db.session.commit()

        job_auto_bill_rent()

        before = RentInvoice.query.filter_by(lease_id=lease.id, period_due_date=due_dates[0]).first()
        after = RentInvoice.query.filter_by(lease_id=lease.id, period_due_date=midpoint).first()
        assert before.amount == lease.monthly_rent
        assert after.amount == lease.monthly_rent + 250


def test_sends_email_notification(app, db, unit, tenant):
    with app.app_context():
        lease = _make_lease(db, unit, tenant, start_offset_days=-40)
        job_auto_bill_rent()
        notifs = Notification.query.filter_by(recipient_id=lease.tenant.user_id, subject="New rent invoice generated").all()
        assert len(notifs) >= 1


def test_auto_bill_rent_registered_in_all_jobs():
    assert job_auto_bill_rent in ALL_JOBS


def test_statement_page_shows_invoices(client, db, owner, unit, tenant):
    lease = _make_lease(db, unit, tenant, start_offset_days=-40)
    job_auto_bill_rent()
    login(client, owner.email)
    resp = client.get(f"/rent/{lease.id}/statement")
    assert resp.status_code == 200
    assert b"Rent Invoices" in resp.data
