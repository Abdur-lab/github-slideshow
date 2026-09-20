from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from backend.extensions import db
from backend.models import (
    MAINT_CATEGORIES,
    MAINT_SEVERITIES,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_OWNER,
    ROLE_STAFF,
    ROLE_TENANT,
    MaintenanceCost,
    MaintenanceNote,
    MaintenanceRequest,
    User,
)
from backend.security import audit_log, current_user, role_required, validate
from backend.services.notifications import send_email, send_sms

MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)
MAX_OPEN_REQUESTS_PER_TENANT = 5

bp = Blueprint("maintenance", __name__, url_prefix="/maintenance")


@bp.route("")
@role_required(*MANAGEMENT_ROLES, ROLE_STAFF)
def index():
    user = current_user()
    query = MaintenanceRequest.query
    if user.role == ROLE_STAFF:
        query = query.filter_by(assigned_to=user.id)
    status_filter = request.args.get("status")
    if status_filter:
        query = query.filter_by(status=status_filter)
    requests = query.order_by(MaintenanceRequest.created_at.desc()).all()
    staff = User.query.filter_by(role=ROLE_STAFF, is_active=True).all()
    return render_template("maintenance/list.html", requests=requests, staff=staff, status_filter=status_filter)


@bp.route("/add", methods=["GET", "POST"])
@role_required(ROLE_TENANT)
def add():
    user = current_user()
    tenant = user.tenant_profile
    if not tenant:
        abort(403)
    lease = tenant.active_lease
    if not lease:
        flash("You do not have an active lease. Please contact your property manager.", "error")
        return redirect(url_for("portal.index"))

    open_count = tenant.maintenance_requests.filter(MaintenanceRequest.status.notin_(["COMPLETED", "CLOSED"])).count()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "OTHER")
        severity = request.form.get("severity", "MEDIUM")

        errors = []
        if open_count >= MAX_OPEN_REQUESTS_PER_TENANT:
            errors.append(f"You already have {MAX_OPEN_REQUESTS_PER_TENANT} open requests. Please wait for one to be resolved.")
        if not title:
            errors.append("Title is required.")
        if not description:
            errors.append("Description is required.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "maintenance/add.html", categories=MAINT_CATEGORIES, severities=MAINT_SEVERITIES, form=request.form
            )

        req = MaintenanceRequest(
            unit_id=lease.unit_id,
            tenant_id=tenant.id,
            ticket_number=MaintenanceRequest.generate_ticket_number(),
            title=title,
            description=description,
            category=category if category in MAINT_CATEGORIES else "OTHER",
            severity=severity if severity in MAINT_SEVERITIES else "MEDIUM",
        )
        db.session.add(req)
        db.session.commit()
        audit_log("maintenance_submitted", "MaintenanceRequest", req.id, new_value={"ticket": req.ticket_number})

        owner = lease.unit.property.owner
        send_email(user, "Maintenance request received", f"Ticket {req.ticket_number} has been received.")
        send_email(owner, "New maintenance request", f"{req.ticket_number}: {title} ({req.severity})")
        if req.severity == "EMERGENCY":
            send_sms(owner, f"EMERGENCY maintenance request {req.ticket_number}: {title}")

        flash(f"Request submitted. Ticket number {req.ticket_number}.", "success")
        return redirect(url_for("portal.index"))

    return render_template("maintenance/add.html", categories=MAINT_CATEGORIES, severities=MAINT_SEVERITIES, form={})


def _can_view(req, user):
    if user.role in MANAGEMENT_ROLES:
        return True
    if user.role == ROLE_STAFF:
        return req.assigned_to == user.id
    if user.role == ROLE_TENANT:
        return user.tenant_profile and req.tenant_id == user.tenant_profile.id
    return False


@bp.route("/<request_id>")
@role_required(*MANAGEMENT_ROLES, ROLE_STAFF, ROLE_TENANT)
def detail(request_id):
    req = MaintenanceRequest.query.get_or_404(request_id)
    if not _can_view(req, current_user()):
        abort(403)
    staff = User.query.filter_by(role=ROLE_STAFF, is_active=True).all()
    return render_template("maintenance/detail.html", req=req, staff=staff)


@bp.route("/<request_id>/update", methods=["POST"])
@role_required(*MANAGEMENT_ROLES, ROLE_STAFF, ROLE_TENANT)
def update(request_id):
    req = MaintenanceRequest.query.get_or_404(request_id)
    user = current_user()
    if not _can_view(req, user):
        abort(403)
    action = request.form.get("action")

    if action == "assign":
        if user.role not in MANAGEMENT_ROLES:
            abort(403)
        staff_id = request.form.get("staff_id")
        target_date_raw = request.form.get("target_date")
        staff = User.query.filter_by(id=staff_id, role=ROLE_STAFF).first()
        if not staff:
            flash("Please choose a valid staff member.", "error")
            return redirect(url_for("maintenance.detail", request_id=req.id))
        req.assigned_to = staff.id
        req.status = "ASSIGNED"
        if target_date_raw and validate("date", target_date_raw):
            req.target_date = date.fromisoformat(target_date_raw)
        elif target_date_raw:
            flash("Target date was invalid and was not saved.", "warning")
        note = request.form.get("notes", "").strip()
        if note:
            db.session.add(MaintenanceNote(request_id=req.id, author_id=user.id, note=note))
        db.session.commit()
        audit_log("maintenance_assigned", "MaintenanceRequest", req.id, new_value={"staff_id": staff.id})
        send_email(staff, "Maintenance request assigned to you", f"Ticket {req.ticket_number}: {req.title}")
        send_email(req.tenant.user, "Your request has been assigned", f"Ticket {req.ticket_number} has been assigned to our team.")
        flash("Request assigned.", "success")

    elif action in ("start", "complete"):
        if user.role != ROLE_STAFF or req.assigned_to != user.id:
            abort(403)
        note_text = request.form.get("notes", "").strip()
        if note_text:
            db.session.add(MaintenanceNote(request_id=req.id, author_id=user.id, note=note_text))
        req.status = "IN_PROGRESS" if action == "start" else "COMPLETED"
        if action == "complete":
            req.completed_at = datetime.utcnow()
        db.session.commit()
        audit_log("maintenance_status_update", "MaintenanceRequest", req.id, new_value={"status": req.status})
        send_email(req.tenant.user, "Maintenance request updated", f"Ticket {req.ticket_number} is now {req.status}.")
        flash("Status updated.", "success")

    elif action in ("close", "reopen"):
        is_owner_tenant = user.role == ROLE_TENANT and user.tenant_profile and req.tenant_id == user.tenant_profile.id
        if not (is_owner_tenant or user.role in MANAGEMENT_ROLES):
            abort(403)
        if req.status != "COMPLETED" and action == "close" and user.role in MANAGEMENT_ROLES:
            pass  # managers may force-close after the 7-day grace window regardless of status
        if action == "close":
            rating = request.form.get("rating")
            req.status = "CLOSED"
            if rating and rating.isdigit():
                req.satisfaction_rating = max(1, min(5, int(rating)))
            db.session.commit()
            audit_log("maintenance_closed", "MaintenanceRequest", req.id)
            flash("Request closed. Thank you!", "success")
        else:
            reason = request.form.get("reason", "").strip()
            req.status = "SUBMITTED"
            req.assigned_to = None
            req.target_date = None
            if reason:
                db.session.add(MaintenanceNote(request_id=req.id, author_id=user.id, note=f"Reopened: {reason}"))
            db.session.commit()
            audit_log("maintenance_reopened", "MaintenanceRequest", req.id, new_value={"reason": reason})
            owner = req.unit.property.owner
            send_email(owner, "Maintenance request reopened", f"Ticket {req.ticket_number} was reopened by the tenant.")
            flash("Request reopened.", "success")
    else:
        abort(400)

    return redirect(url_for("maintenance.detail", request_id=req.id))


@bp.route("/<request_id>/costs/add", methods=["POST"])
@role_required(*MANAGEMENT_ROLES)
def add_cost(request_id):
    req = MaintenanceRequest.query.get_or_404(request_id)
    amount = request.form.get("amount")
    category = request.form.get("category", "OTHER")
    description = request.form.get("description", "").strip()

    if not validate("positive_float", amount):
        flash("Cost amount must be a positive number.", "error")
        return redirect(url_for("maintenance.detail", request_id=req.id))

    cost = MaintenanceCost(
        request_id=req.id,
        category=category,
        amount=float(amount),
        currency=req.unit.property.currency,
        description=description,
        recorded_by=current_user().id,
    )
    db.session.add(cost)
    db.session.commit()
    audit_log("maintenance_cost_logged", "MaintenanceCost", cost.id, new_value={"amount": float(amount)})
    flash("Cost logged.", "success")
    return redirect(url_for("maintenance.detail", request_id=req.id))
