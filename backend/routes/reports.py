from datetime import date, datetime

from flask import Blueprint, Response, render_template, request

from backend.models import ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER, Property
from backend.security import assert_owner, audit_log, current_user, role_required
from backend.services.pdf import render_property_report_pdf
from backend.services.reports import portfolio_performance, property_performance

MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _visible_properties(user):
    q = Property.query.filter_by(status="ACTIVE")
    if user.role == ROLE_OWNER:
        q = q.filter_by(owner_id=user.id)
    return q.all()


@bp.route("")
@role_required(*MANAGEMENT_ROLES)
def index():
    user = current_user()
    properties = _visible_properties(user)
    property_id = request.args.get("property_id")
    if property_id:
        assert_owner(property_id)
        prop = Property.query.get_or_404(property_id)
        summary = property_performance(prop)
    else:
        prop = None
        summary = portfolio_performance(properties)
    audit_log("report_viewed", "Property", property_id)
    return render_template("reports/index.html", properties=properties, selected=prop, summary=summary)


@bp.route("/export.pdf")
@role_required(*MANAGEMENT_ROLES)
def export_pdf():
    user = current_user()
    property_id = request.args.get("property_id")
    if property_id:
        assert_owner(property_id)
        prop = Property.query.get_or_404(property_id)
        summary = property_performance(prop)
        pdf_bytes = render_property_report_pdf(prop, summary)
        filename = f"report-{prop.property_code}.pdf"
    else:
        properties = _visible_properties(user)
        summary = portfolio_performance(properties)

        class _Portfolio:
            name = "All Properties (Portfolio)"
            property_code = "PORTFOLIO"

        flat_summary = {k: v for k, v in summary.items() if k != "properties"}
        pdf_bytes = render_property_report_pdf(_Portfolio(), flat_summary)
        filename = "report-portfolio.pdf"
    audit_log("report_exported", "Property", property_id, new_value={"format": "pdf"})
    return Response(pdf_bytes, mimetype="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})
