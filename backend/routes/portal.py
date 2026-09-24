from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from backend.models import ROLE_TENANT, Lease, MaintenanceRequest, RentPayment
from backend.security import audit_log, current_user, role_required
from backend.services.notifications import send_email
from backend.services.payments import create_checkout_session, record_idempotent_payment

bp = Blueprint("portal", __name__, url_prefix="/portal")


def _my_tenant():
    user = current_user()
    if not user.tenant_profile:
        abort(403)
    return user.tenant_profile


@bp.route("")
@role_required(ROLE_TENANT)
def index():
    tenant = _my_tenant()
    lease = tenant.active_lease
    recent_payments = lease.payments.order_by(RentPayment.paid_at.desc()).limit(5).all() if lease else []
    requests = tenant.maintenance_requests.order_by(MaintenanceRequest.created_at.desc()).all()
    return render_template("portal/dashboard.html", tenant=tenant, lease=lease, recent_payments=recent_payments, requests=requests)


@bp.route("/pay", methods=["GET", "POST"])
@role_required(ROLE_TENANT)
def pay():
    tenant = _my_tenant()
    lease = tenant.active_lease
    if not lease:
        flash("You do not have an active lease.", "error")
        return redirect(url_for("portal.index"))
    if request.method == "POST":
        amount = lease.balance
        if amount <= 0:
            flash("You have no outstanding balance.", "info")
            return redirect(url_for("portal.index"))
        session_info = create_checkout_session(lease, amount)
        return redirect(session_info["checkout_url"])
    return render_template("portal/pay_rent.html", tenant=tenant, lease=lease)


@bp.route("/pay/confirm/<lease_id>")
@role_required(ROLE_TENANT)
def pay_confirm(lease_id):
    """Dev-mode Stripe redirect target: simulates the gateway's success
    callback so the online-payment flow (UC-13) is testable end-to-end
    without a live Stripe account."""
    tenant = _my_tenant()
    lease = Lease.query.get_or_404(lease_id)
    if lease.tenant_id != tenant.id:
        abort(403)
    ref = request.args.get("ref")
    amount = lease.balance
    if amount <= 0 or not ref:
        flash("Nothing to confirm.", "info")
        return redirect(url_for("portal.index"))
    payment = record_idempotent_payment(lease, amount, ref, recorded_by=current_user().id, method="ONLINE")
    audit_log("rent_paid_online", "RentPayment", payment.id, new_value={"amount": amount, "lease_id": lease.id})
    send_email(tenant.user, "Payment received", f"We received your online payment of {payment.amount:.2f} ({payment.receipt_number}).")
    send_email(lease.unit.property.owner, "Tenant payment received", f"{tenant.user.full_name} paid {payment.amount:.2f} online.")
    flash("Payment successful. Thank you!", "success")
    return redirect(url_for("portal.index"))


@bp.route("/history")
@role_required(ROLE_TENANT)
def history():
    tenant = _my_tenant()
    lease = tenant.active_lease
    payments = lease.payments.order_by(RentPayment.paid_at.desc()).all() if lease else []
    return render_template("portal/rent_history.html", tenant=tenant, lease=lease, payments=payments)
