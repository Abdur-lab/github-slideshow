import csv
import io
from datetime import date

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from backend.extensions import db
from backend.models import (
    CHARGE_TYPES,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_OWNER,
    ROLE_TENANT,
    Lease,
    LeaseCharge,
    MeterReading,
    PAYMENT_METHODS,
    RentPayment,
    Tenant,
)
from backend.security import assert_tenant_self, audit_log, current_user, role_required, validate
from backend.services.notifications import send_email
from backend.services.pdf import render_rent_statement_pdf

MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)

bp = Blueprint("rent", __name__, url_prefix="/rent")


@bp.route("")
@role_required(*MANAGEMENT_ROLES)
def index():
    leases = Lease.query.filter_by(status="ACTIVE").all()
    rows = sorted(leases, key=lambda l: l.balance, reverse=True)
    return render_template("rent/tracker.html", leases=rows)


@bp.route("/record", methods=["GET", "POST"])
@role_required(*MANAGEMENT_ROLES)
def record():
    lease_id = request.args.get("lease_id") or request.form.get("lease_id")
    lease = db.session.get(Lease, lease_id) if lease_id else None
    active_leases = Lease.query.filter_by(status="ACTIVE").all()

    if request.method == "POST":
        amount = request.form.get("amount")
        method = request.form.get("method", "CASH")
        paid_at_raw = request.form.get("paid_at")
        notes = request.form.get("notes", "").strip()

        errors = []
        if not lease:
            errors.append("Please select a tenant/lease.")
        if not validate("positive_float", amount):
            errors.append("Amount must be a positive number.")
        paid_at = date.today()
        if paid_at_raw:
            if not validate("date", paid_at_raw):
                errors.append("Payment date is invalid.")
            else:
                paid_at = date.fromisoformat(paid_at_raw)
                if paid_at > date.today():
                    flash("Payment date is in the future — please confirm this is correct.", "warning")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("rent/record_payment.html", lease=lease, active_leases=active_leases, methods=PAYMENT_METHODS)

        payment = RentPayment(
            lease_id=lease.id,
            amount=float(amount),
            method=method if method in PAYMENT_METHODS else "CASH",
            receipt_number=RentPayment.generate_receipt_number(),
            paid_at=paid_at,
            recorded_by=current_user().id,
            notes=notes,
        )
        db.session.add(payment)
        db.session.commit()
        audit_log("rent_payment_recorded", "RentPayment", payment.id, new_value={"amount": float(amount), "lease_id": lease.id})
        send_email(
            lease.tenant.user,
            "Rent payment received",
            f"We received your payment of {payment.amount:.2f} ({payment.receipt_number}). Remaining balance: {lease.balance:.2f}.",
        )
        flash(f"Payment recorded. Receipt {payment.receipt_number}.", "success")
        return redirect(url_for("rent.index"))

    return render_template("rent/record_payment.html", lease=lease, active_leases=active_leases, methods=PAYMENT_METHODS)


@bp.route("/<lease_id>/history")
@role_required(*MANAGEMENT_ROLES)
def history(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    payments = lease.payments.order_by(RentPayment.paid_at.desc()).all()
    return render_template("rent/history.html", lease=lease, payments=payments)


@bp.route("/<lease_id>/history.csv")
@role_required(*MANAGEMENT_ROLES, ROLE_TENANT)
def history_csv(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    assert_tenant_self(lease.tenant_id)
    payments = lease.payments.order_by(RentPayment.paid_at.asc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "Type", "Amount", "Method", "Receipt Number", "Notes"])
    for p in payments:
        writer.writerow([p.paid_at.date().isoformat(), "Payment", f"{p.amount:.2f}", p.method, p.receipt_number, p.notes or ""])
    audit_log("rent_history_exported", "Lease", lease.id, new_value={"format": "csv"})
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=rent-history-{lease.id[:8]}.csv"},
    )


@bp.route("/<lease_id>/statement")
@role_required(*MANAGEMENT_ROLES)
def statement(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    payments = lease.payments.order_by(RentPayment.paid_at.desc()).all()
    charges = lease.charges.order_by(LeaseCharge.charged_at.desc()).all()
    meter_readings = lease.unit.meter_readings.order_by(MeterReading.reading_date.desc(), MeterReading.created_at.desc()).limit(10).all()
    return render_template(
        "rent/statement.html",
        lease=lease,
        payments=payments,
        charges=charges,
        charge_types=CHARGE_TYPES,
        meter_readings=meter_readings,
        today=date.today(),
    )


@bp.route("/<lease_id>/charges/add", methods=["POST"])
@role_required(*MANAGEMENT_ROLES)
def add_charge(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    charge_type = request.form.get("charge_type", "OPERATIONAL")
    description = request.form.get("description", "").strip()
    amount = request.form.get("amount")

    errors = []
    if charge_type not in CHARGE_TYPES:
        charge_type = "OPERATIONAL"
    if not description:
        errors.append("A description is required for the charge.")
    if not validate("positive_float", amount):
        errors.append("Charge amount must be a positive number.")
    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("rent.statement", lease_id=lease.id))

    charge = LeaseCharge(
        lease_id=lease.id,
        charge_type=charge_type,
        description=description,
        amount=float(amount),
        recorded_by=current_user().id,
    )
    db.session.add(charge)
    db.session.commit()
    audit_log("lease_charge_added", "LeaseCharge", charge.id, new_value={"charge_type": charge_type, "amount": float(amount)})
    send_email(
        lease.tenant.user,
        "A new charge was added to your account",
        f"A {charge_type.title()} charge of {charge.amount:.2f} ({description}) was added to your unit {lease.unit.unit_code}. "
        f"Updated balance: {lease.balance:.2f}.",
    )
    flash(f"{charge_type.title()} charge of {charge.amount:.2f} added.", "success")
    return redirect(url_for("rent.statement", lease_id=lease.id))


@bp.route("/<lease_id>/meter/add-reading", methods=["POST"])
@role_required(*MANAGEMENT_ROLES)
def add_meter_reading(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    unit = lease.unit
    reading_date_raw = request.form.get("reading_date")
    reading_value_raw = request.form.get("reading_value")

    errors = []
    reading_date = date.today()
    if reading_date_raw:
        if not validate("date", reading_date_raw):
            errors.append("Reading date is invalid.")
        else:
            reading_date = date.fromisoformat(reading_date_raw)

    try:
        reading_value = float(reading_value_raw)
        if reading_value < 0:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Meter reading must be a non-negative number.")
        reading_value = None

    previous = unit.latest_meter_reading
    if reading_value is not None and previous is not None and reading_value < previous.reading_value:
        errors.append(f"Reading ({reading_value}) is lower than the last recorded reading ({previous.reading_value}).")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("rent.statement", lease_id=lease.id))

    consumption = None
    amount = 0.0
    if previous is not None:
        consumption = round(reading_value - previous.reading_value, 2)
        amount = round(consumption * unit.property.electricity_rate, 2)

    reading = MeterReading(
        unit_id=unit.id,
        reading_date=reading_date,
        reading_value=reading_value,
        consumption=consumption,
        rate_applied=unit.property.electricity_rate if previous is not None else None,
        recorded_by=current_user().id,
    )
    db.session.add(reading)
    db.session.flush()

    if consumption is not None and amount > 0 and unit.active_lease:
        charge = LeaseCharge(
            lease_id=unit.active_lease.id,
            charge_type="ELECTRICITY",
            description=f"Electricity: {consumption} units @ {unit.property.electricity_rate:.2f}",
            amount=amount,
            recorded_by=current_user().id,
        )
        db.session.add(charge)
        db.session.flush()
        reading.charge_id = charge.id
        db.session.commit()
        audit_log("meter_reading_added", "MeterReading", reading.id, new_value={"reading_value": reading_value, "charge_amount": amount})
        send_email(
            unit.active_lease.tenant.user,
            "A new electricity charge was added to your account",
            f"An electricity charge of {amount:.2f} ({consumption} units) was added to your unit {unit.unit_code}. "
            f"Updated balance: {unit.active_lease.balance:.2f}.",
        )
        flash(f"Reading recorded. Electricity charge of {amount:.2f} added.", "success")
    else:
        db.session.commit()
        audit_log("meter_reading_added", "MeterReading", reading.id, new_value={"reading_value": reading_value})
        if consumption is not None and not unit.active_lease:
            flash("Reading recorded. This unit has no active lease, so no charge was billed.", "warning")
        else:
            flash("Reading recorded as the baseline for this unit.", "success")

    return redirect(url_for("rent.statement", lease_id=lease.id))


@bp.route("/<lease_id>/statement.pdf")
@role_required(*MANAGEMENT_ROLES)
def statement_pdf(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    payments = lease.payments.order_by(RentPayment.paid_at.asc()).all()
    charges = lease.charges.order_by(LeaseCharge.charged_at.asc()).all()
    pdf_bytes = render_rent_statement_pdf(lease, payments, current_user().full_name, charges=charges)
    audit_log("rent_statement_exported", "Lease", lease.id)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=statement-{lease.id[:8]}.pdf"},
    )
