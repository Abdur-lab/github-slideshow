from datetime import date, timedelta

from flask import Blueprint, jsonify, render_template

from backend.models import ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER, Lease, MaintenanceRequest, Property, Unit
from backend.security import current_user, role_required
from backend.services.reports import portfolio_performance

bp = Blueprint("dashboard", __name__)


def visible_properties(user):
    q = Property.query.filter_by(status="ACTIVE")
    if user.role == ROLE_OWNER:
        q = q.filter_by(owner_id=user.id)
    return q.all()


@bp.route("/dashboard")
@role_required(ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)
def index():
    user = current_user()
    properties = visible_properties(user)
    summary = portfolio_performance(properties)
    unit_ids = [u.id for p in properties for u in p.units]
    expiring = (
        Lease.query.filter(
            Lease.unit_id.in_(unit_ids),
            Lease.status == "ACTIVE",
            Lease.end_date <= date.today() + timedelta(days=30),
            Lease.end_date >= date.today(),
        ).all()
        if unit_ids
        else []
    )
    open_maintenance = (
        MaintenanceRequest.query.filter(
            MaintenanceRequest.unit_id.in_(unit_ids),
            MaintenanceRequest.status.notin_(["COMPLETED", "CLOSED"]),
        ).all()
        if unit_ids
        else []
    )
    return render_template(
        "dashboard.html", properties=properties, summary=summary, expiring=expiring, open_maintenance=open_maintenance
    )


@bp.route("/api/v1/dashboard-stats")
@role_required(ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)
def stats():
    user = current_user()
    return jsonify(portfolio_performance(visible_properties(user)))
