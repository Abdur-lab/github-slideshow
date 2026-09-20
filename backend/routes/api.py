from flask import Blueprint, current_app, jsonify, request

from backend.extensions import csrf, db
from backend.models import ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER, ROLE_TENANT, Lease, Notification, Property, RentPayment
from backend.security import assert_tenant_self, audit_log, current_user, role_required
from backend.services.payments import record_idempotent_payment, verify_stripe_signature
from backend.services.reports import portfolio_performance

MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)

bp = Blueprint("api", __name__, url_prefix="/api/v1")


@bp.route("/leases/<lease_id>/statement")
@role_required(*MANAGEMENT_ROLES, ROLE_TENANT)
def lease_statement(lease_id):
    lease = Lease.query.get_or_404(lease_id)
    assert_tenant_self(lease.tenant_id)
    payments = lease.payments.order_by(RentPayment.paid_at).all()
    return jsonify(
        {
            "lease_id": lease.id,
            "tenant": lease.tenant.user.full_name,
            "unit": lease.unit.unit_code,
            "start_date": str(lease.start_date),
            "end_date": str(lease.end_date),
            "monthly_rent": lease.monthly_rent,
            "total_due": lease.total_due_to_date(),
            "total_paid": lease.total_paid,
            "balance": lease.balance,
            "payments": [
                {"amount": p.amount, "method": p.method, "receipt_number": p.receipt_number, "paid_at": str(p.paid_at)}
                for p in payments
            ],
        }
    )


@bp.route("/webhooks/stripe", methods=["POST"])
@csrf.exempt
def stripe_webhook():
    secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
    sig_header = request.headers.get("Stripe-Signature", "")
    payload = request.get_data()

    if secret and not verify_stripe_signature(payload, sig_header, secret):
        return jsonify({"error": "invalid signature"}), 400

    data = request.get_json(silent=True) or {}
    event_type = data.get("type")
    obj = data.get("data", {}).get("object", {})
    lease_id = obj.get("metadata", {}).get("lease_id")
    gateway_ref = obj.get("id")
    amount_cents = obj.get("amount", 0)

    if event_type == "payment_intent.succeeded" and lease_id and gateway_ref:
        lease = db.session.get(Lease, lease_id)
        if lease:
            payment = record_idempotent_payment(
                lease, amount_cents / 100.0, gateway_ref, recorded_by=lease.tenant.user_id, method="ONLINE"
            )
            audit_log("stripe_webhook_payment", "RentPayment", payment.id)
    return jsonify({"received": True})


@bp.route("/notifications/mark-read", methods=["POST"])
def mark_notifications_read():
    user = current_user()
    if user is None:
        return jsonify({"error": "unauthorized"}), 401
    Notification.query.filter_by(recipient_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"success": True})


@bp.route("/reports/export")
@role_required(*MANAGEMENT_ROLES)
def reports_export():
    user = current_user()
    q = Property.query.filter_by(status="ACTIVE")
    if user.role == ROLE_OWNER:
        q = q.filter_by(owner_id=user.id)
    properties = q.all()
    summary = portfolio_performance(properties)
    audit_log("report_exported", "Property", None, new_value={"format": "json"})
    return jsonify(
        {
            "summary": {k: v for k, v in summary.items() if k != "properties"},
            "properties": summary["properties"],
            "monthly_rent": sum(u.monthly_rent for p in properties for u in p.units),
        }
    )
