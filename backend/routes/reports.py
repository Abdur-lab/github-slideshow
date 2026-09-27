from datetime import date, datetime

from flask import Blueprint, Response, flash, render_template, request

from backend.models import ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER, Property
from backend.security import assert_owner, audit_log, current_user, role_required
from backend.services.excel import render_portfolio_report_xlsx
from backend.services.pdf import render_property_report_pdf
from backend.services.reports import maintenance_summary, portfolio_performance, property_performance

MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _visible_properties(user):
    q = Property.query.filter_by(status="ACTIVE")
    if user.role == ROLE_OWNER:
        q = q.filter_by(owner_id=user.id)
    return q.all()


def _maintenance_period(args):
    """The maintenance summary's date range from ?start=&end= (YYYY-MM-DD),
    defaulting to the current month to date."""
    today = date.today()
    default = (today.replace(day=1), today)
    raw_start, raw_end = args.get("start"), args.get("end")
    if not raw_start and not raw_end:
        return default
    try:
        start = date.fromisoformat(raw_start) if raw_start else default[0]
        end = date.fromisoformat(raw_end) if raw_end else today
    except ValueError:
        flash("Dates must be in YYYY-MM-DD format; showing the current month instead.", "error")
        return default
    if start > end:
        flash("The start date must be on or before the end date; showing the current month instead.", "error")
        return default
    return start, end


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
    start, end = _maintenance_period(request.args)
    maintenance = maintenance_summary([prop] if prop else properties, start, end)
    audit_log("report_viewed", "Property", property_id)
    return render_template("reports/index.html", properties=properties, selected=prop, summary=summary, maintenance=maintenance)


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


@bp.route("/export.xlsx")
@role_required(*MANAGEMENT_ROLES)
def export_xlsx():
    user = current_user()
    property_id = request.args.get("property_id")
    if property_id:
        assert_owner(property_id)
        prop = Property.query.get_or_404(property_id)
        prop_summary = property_performance(prop)
        summary = {**prop_summary, "properties": [prop_summary]}
        filename = f"report-{prop.property_code}.xlsx"
    else:
        properties = _visible_properties(user)
        summary = portfolio_performance(properties)
        filename = "report-portfolio.xlsx"
    xlsx_bytes = render_portfolio_report_xlsx(summary)
    audit_log("report_exported", "Property", property_id, new_value={"format": "xlsx"})
    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
