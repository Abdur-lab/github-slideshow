"""The five APScheduler background jobs (UC-11, UC-14, auto billing, UC-15, UC-23).

Each job assumes it is called from within an active Flask app context —
either pushed by the scheduler wrapper in backend/__init__.py for real
scheduled runs, or by the test fixture when called directly, matching how
Deliverable 3 describes the test suite invoking these jobs."""
from datetime import date, datetime, timedelta

from backend.extensions import db
from backend.models import Lease, MaintenanceRequest, RentInvoice, ROLE_MANAGER, ROLE_OWNER, User
from backend.security import audit_log
from backend.services.notifications import send_email, send_sms

LEASE_EXPIRY_THRESHOLDS = (60, 30, 7)
RENT_DUE_THRESHOLDS = (7, 1)


def job_lease_expiry_alerts() -> int:
    """UC-11: notify tenant + owner exactly 60/30/7 days before lease end."""
    today = date.today()
    sent = 0
    for days in LEASE_EXPIRY_THRESHOLDS:
        target = today + timedelta(days=days)
        leases = Lease.query.filter(Lease.status == "ACTIVE", Lease.end_date == target).all()
        for lease in leases:
            tenant_user = lease.tenant.user
            owner = lease.unit.property.owner
            body = f"Lease for unit {lease.unit.unit_code} at {lease.unit.property.name} expires on {lease.end_date} ({days} days remaining)."
            send_email(tenant_user, "Your lease is expiring soon", body)
            send_email(owner, f"Tenant lease expiring in {days} days", f"{tenant_user.full_name}: {body}")
            audit_log("lease_expiry_alert", "Lease", lease.id, new_value={"days_remaining": days})
            sent += 1
    return sent


def job_rent_due_alerts() -> int:
    """UC-14: notify tenants whose rent is due in exactly 7 or 1 days and
    who have not yet paid for the current period."""
    today = date.today()
    sent = 0
    for lease in Lease.query.filter_by(status="ACTIVE").all():
        if lease.balance <= 0:
            continue
        next_due = lease.next_due_date(today)
        days_out = (next_due - today).days
        if days_out not in RENT_DUE_THRESHOLDS:
            continue
        tenant_user = lease.tenant.user
        body = f"Rent of {lease.balance:.2f} for unit {lease.unit.unit_code} is due on {next_due}."
        send_email(tenant_user, "Rent due soon", body)
        send_sms(tenant_user, body)
        audit_log("rent_due_alert", "Lease", lease.id, new_value={"days_out": days_out})
        sent += 1
    return sent


def job_auto_bill_rent() -> int:
    """Automated recurring billing: for each active lease, generates a
    RentInvoice for every elapsed billing period that hasn't been billed
    yet, at the rent in effect for that period (Lease.amount_for_period —
    honouring pro_rata proration and any rent revision), and emails the
    tenant a notice. Walking from the lease's first due date catches up
    on any periods missed by a prior run, and the (lease_id,
    period_due_date) uniqueness on RentInvoice makes re-running the job
    for an already-billed period a no-op rather than a double charge."""
    today = date.today()
    sent = 0
    for lease in Lease.query.filter_by(status="ACTIVE").all():
        already_billed = {inv.period_due_date for inv in lease.invoices.all()}
        for due in lease.due_dates_to_date(today):
            if due in already_billed:
                continue
            amount = lease.amount_for_period(due)
            invoice = RentInvoice(lease_id=lease.id, period_due_date=due, amount=amount)
            db.session.add(invoice)
            tenant_user = lease.tenant.user
            body = (
                f"A rent invoice of {amount:.2f} for unit {lease.unit.unit_code} has been generated for the "
                f"billing period due {due}. Current balance: {lease.balance:.2f}."
            )
            send_email(tenant_user, "New rent invoice generated", body)
            audit_log("rent_auto_billed", "Lease", lease.id, new_value={"period_due_date": str(due), "amount": amount})
            sent += 1
    db.session.commit()
    return sent


def job_overdue_alerts() -> int:
    """UC-15: escalating overdue notices to the tenant, plus a daily
    summary to each property owner."""
    today = date.today()
    sent = 0
    owner_summaries: dict[str, list] = {}
    for lease in Lease.query.filter_by(status="ACTIVE").all():
        if lease.balance <= 0:
            continue
        current_due = lease.current_due_date(today)
        if current_due is None or current_due >= today:
            continue
        days_overdue = (today - current_due).days
        if days_overdue <= 0:
            continue
        if days_overdue <= 3:
            tier = "Gentle reminder"
        elif days_overdue <= 7:
            tier = "Firm notice — late fee may apply"
        else:
            tier = "Final notice — escalation warning"
        tenant_user = lease.tenant.user
        body = f"[{tier}] Rent of {lease.balance:.2f} is {days_overdue} day(s) overdue."
        send_email(tenant_user, "Overdue rent notice", body)
        send_sms(tenant_user, body)
        audit_log("overdue_notice", "Lease", lease.id, new_value={"days_overdue": days_overdue, "tier": tier})
        sent += 1

        owner = lease.unit.property.owner
        owner_summaries.setdefault(owner.id, []).append(lease)

    for owner_id, leases in owner_summaries.items():
        owner = db.session.get(User, owner_id)
        total = sum(l.balance for l in leases)
        body = f"{len(leases)} tenant(s) overdue, totalling {total:.2f} outstanding."
        send_email(owner, "Daily overdue rent summary", body)
        sent += 1
    return sent


def job_escalate_overdue_maintenance() -> int:
    """UC-23: escalate requests past their target completion date, plus
    emergency-severity requests unacknowledged for over 2 hours."""
    today = date.today()
    now = datetime.utcnow()
    sent = 0

    open_requests = MaintenanceRequest.query.filter(MaintenanceRequest.status.in_(("ASSIGNED", "IN_PROGRESS"))).all()
    for req in open_requests:
        if req.target_date and req.target_date < today:
            req.escalated = True
            owner = req.unit.property.owner
            days_over = (today - req.target_date).days
            body = f"Ticket {req.ticket_number} is {days_over} day(s) past its target completion date."
            send_email(owner, "Overdue maintenance escalation", body)
            audit_log("maintenance_escalation", "MaintenanceRequest", req.id, new_value={"days_overdue": days_over})
            sent += 1
            if days_over >= 7:
                for manager in User.query.filter_by(role=ROLE_MANAGER).all():
                    send_email(manager, "Overdue maintenance escalation", body)

    db.session.commit()

    unacknowledged = MaintenanceRequest.query.filter_by(status="SUBMITTED", severity="EMERGENCY").all()
    for req in unacknowledged:
        age = now - req.created_at
        if age > timedelta(hours=2):
            owner = req.unit.property.owner
            body = f"EMERGENCY ticket {req.ticket_number} has not been acknowledged in over 2 hours."
            send_email(owner, "Emergency maintenance not acknowledged", body)
            for manager in User.query.filter_by(role=ROLE_MANAGER).all():
                send_email(manager, "Emergency maintenance not acknowledged", body)
            audit_log("maintenance_emergency_escalation", "MaintenanceRequest", req.id)
            sent += 1
    return sent


ALL_JOBS = (
    job_lease_expiry_alerts,
    job_rent_due_alerts,
    job_auto_bill_rent,
    job_overdue_alerts,
    job_escalate_overdue_maintenance,
)
