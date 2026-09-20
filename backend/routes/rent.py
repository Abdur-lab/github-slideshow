from datetime import date

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from backend.extensions import db
from backend.models import ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER, Lease, PAYMENT_METHODS, RentPayment, Tenant
from backend.security import audit_log, current_user, role_required, validate
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


@bp.route("/<lease_id>/statement")
@role_required(*MANAGEMENT_ROLES)
def statement(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    payments = lease.payments.order_by(RentPayment.paid_at.desc()).all()
    return render_template("rent/statement.html", lease=lease, payments=payments)


@bp.route("/<lease_id>/statement.pdf")
@role_required(*MANAGEMENT_ROLES)
def statement_pdf(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    payments = lease.payments.order_by(RentPayment.paid_at.asc()).all()
    pdf_bytes = render_rent_statement_pdf(lease, payments, current_user().full_name)
    audit_log("rent_statement_exported", "Lease", lease.id)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=statement-{lease.id[:8]}.pdf"},
    )
