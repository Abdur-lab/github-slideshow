from datetime import date, datetime, timedelta

import pytest

from backend.extensions import db
from backend.models import AuditLog, Lease, MaintenanceRequest, Notification, RentPayment, Unit
from backend.scheduler_jobs import (
    job_escalate_overdue_maintenance,
    job_lease_expiry_alerts,
    job_overdue_alerts,
    job_rent_due_alerts,
)
from backend.security import audit_log


def _make_lease(db, unit, tenant, start_offset_days, end_offset_days, due_day=1):
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=date.today() + timedelta(days=start_offset_days),
        end_date=date.today() + timedelta(days=end_offset_days),
        monthly_rent=unit.monthly_rent,
        deposit=unit.deposit,
        due_day=due_day,
    )
    db.session.add(lease)
    db.session.commit()
    return lease


def test_lease_expiry_alert_fires_at_30_days(app, db, unit, tenant):
    with app.app_context():
        lease = _make_lease(db, unit, tenant, start_offset_days=-300, end_offset_days=30)
        sent = job_lease_expiry_alerts()
        assert sent == 1
        notifs = Notification.query.filter_by(recipient_id=lease.tenant.user_id).all()
        assert any("expir" in (n.body or "").lower() for n in notifs)
        owner_notifs = Notification.query.filter_by(recipient_id=lease.unit.property.owner_id).all()
        assert len(owner_notifs) >= 1


def test_lease_expiry_alert_skips_at_100_days(app, db, unit, tenant):
    with app.app_context():
        _make_lease(db, unit, tenant, start_offset_days=-260, end_offset_days=100)
        sent = job_lease_expiry_alerts()
        assert sent == 0


def test_rent_due_alert_fires_at_7_and_1_day_thresholds(app, db, property_, tenant):
    # due_day recurs monthly, so we pin each test lease's due_day to the
    # day-of-month that lands exactly 7 (then 1) days from today. Skipped
    # very close to month-end, where day-of-month clipping (_clip_day) in a
    # short month could shift the actual due date by a day.
    with app.app_context():
        for i, days_out in enumerate((7, 1)):
            target = date.today() + timedelta(days=days_out)
            if target.day > 28:
                pytest.skip("near month-end; due-day clipping could shift the target date")
            new_unit = Unit(
                property_id=property_.id,
                unit_number=f"DUE{i}",
                monthly_rent=1000.0,
                unit_code=Unit.generate_unit_code(property_.property_code, f"DUE{i}"),
            )
            db.session.add(new_unit)
            db.session.commit()
            lease = _make_lease(db, new_unit, tenant, start_offset_days=-100, end_offset_days=300, due_day=target.day)
            assert lease.next_due_date() == target
            assert lease.balance > 0
        sent = job_rent_due_alerts()
        assert sent == 2


def test_rent_due_alert_skips_when_fully_paid(app, db, unit, tenant):
    with app.app_context():
        lease = _make_lease(db, unit, tenant, start_offset_days=-40, end_offset_days=325)
        db.session.add(
            RentPayment(
                lease_id=lease.id,
                amount=lease.total_due_to_date() + 1000,
                method="CASH",
                receipt_number=RentPayment.generate_receipt_number(),
                recorded_by=lease.tenant.user_id,
            )
        )
        db.session.commit()
        assert lease.balance == 0.0
        sent = job_rent_due_alerts()
        assert sent == 0


def test_overdue_alert_creates_notification_and_owner_summary(app, db, unit, tenant):
    # Pin due_day to 15 days ago so the current period is unambiguously
    # overdue regardless of what day-of-month "today" happens to be.
    with app.app_context():
        overdue_due_day = (date.today() - timedelta(days=15)).day
        if overdue_due_day > 28:
            pytest.skip("near month-end; due-day clipping could shift the target date")
        lease = _make_lease(db, unit, tenant, start_offset_days=-70, end_offset_days=295, due_day=overdue_due_day)
        assert lease.balance > 0
        sent = job_overdue_alerts()
        assert sent >= 1
        tenant_notifs = Notification.query.filter_by(recipient_id=lease.tenant.user_id).all()
        assert any("overdue" in (n.body or "").lower() for n in tenant_notifs)
        owner_notifs = Notification.query.filter_by(recipient_id=lease.unit.property.owner_id, subject="Daily overdue rent summary").all()
        assert len(owner_notifs) == 1


def test_maintenance_escalation_fires_for_open_overdue(app, db, unit, tenant, staff):
    with app.app_context():
        req = MaintenanceRequest(
            unit_id=unit.id,
            tenant_id=tenant.id,
            ticket_number=MaintenanceRequest.generate_ticket_number(),
            title="Overdue job",
            description="x",
            status="ASSIGNED",
            assigned_to=staff.id,
            target_date=date.today() - timedelta(days=3),
        )
        db.session.add(req)
        db.session.commit()
        sent = job_escalate_overdue_maintenance()
        assert sent >= 1
        db.session.refresh(req)
        assert req.escalated is True


def test_maintenance_escalation_skips_closed(app, db, unit, tenant, staff):
    with app.app_context():
        req = MaintenanceRequest(
            unit_id=unit.id,
            tenant_id=tenant.id,
            ticket_number=MaintenanceRequest.generate_ticket_number(),
            title="Closed job",
            description="x",
            status="CLOSED",
            assigned_to=staff.id,
            target_date=date.today() - timedelta(days=3),
        )
        db.session.add(req)
        db.session.commit()
        job_escalate_overdue_maintenance()
        db.session.refresh(req)
        assert req.escalated is False


def test_maintenance_escalation_skips_future_target_dates(app, db, unit, tenant, staff):
    with app.app_context():
        req = MaintenanceRequest(
            unit_id=unit.id,
            tenant_id=tenant.id,
            ticket_number=MaintenanceRequest.generate_ticket_number(),
            title="Future job",
            description="x",
            status="ASSIGNED",
            assigned_to=staff.id,
            target_date=date.today() + timedelta(days=3),
        )
        db.session.add(req)
        db.session.commit()
        job_escalate_overdue_maintenance()
        db.session.refresh(req)
        assert req.escalated is False


def test_audit_log_safe_outside_request_context(app):
    with app.app_context():
        entry = audit_log("scheduler_test", "System", None)
        assert entry.ip_address == "scheduler"
        assert entry.user_id is None
