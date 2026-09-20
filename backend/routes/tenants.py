import os
import secrets
from datetime import date

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from backend.extensions import db
from backend.models import ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER, ROLE_TENANT, Lease, PasswordReset, Property, Tenant, Unit, User
from backend.security import assert_owner, audit_log, role_required, validate, validate_upload
from backend.services.notifications import send_email, send_email_raw

MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)

bp = Blueprint("tenants", __name__, url_prefix="/tenants")


@bp.route("")
@role_required(*MANAGEMENT_ROLES)
def index():
    tenants = Tenant.query.join(User).order_by(User.last_name, User.first_name).all()
    return render_template("tenants/list.html", tenants=tenants)


@bp.route("/add", methods=["GET", "POST"])
@role_required(*MANAGEMENT_ROLES)
def add():
    unit_id = request.args.get("unit_id") or request.form.get("unit_id")
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        national_id = request.form.get("national_id", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        emergency_contact = request.form.get("emergency_contact", "").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not national_id:
            errors.append("National ID is required.")
        elif Tenant.query.filter_by(national_id=national_id).first():
            errors.append("A tenant with this national ID may already exist. Please search before creating a new one.")
        if email and not validate("email", email):
            errors.append("Email address is invalid.")
        if email and User.query.filter_by(email=email).first():
            errors.append("A user with this email already exists.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("tenants/add.html", form=request.form, unit_id=unit_id)

        if not email:
            email = f"tenant-{secrets.token_hex(4)}@no-email.rentalpro.invalid"
        first_name, _, last_name = full_name.partition(" ")
        user = User(email=email, first_name=first_name or full_name, last_name=last_name or "-", role=ROLE_TENANT)
        user.set_password(secrets.token_urlsafe(16))
        db.session.add(user)
        db.session.flush()
        tenant = Tenant(user_id=user.id, national_id=national_id, phone=phone, emergency_contact=emergency_contact)
        db.session.add(tenant)
        db.session.commit()
        audit_log("tenant_created", "Tenant", tenant.id, new_value={"national_id": national_id})

        if "@no-email.rentalpro.invalid" not in email:
            reset = PasswordReset(user_id=user.id, expires_at=PasswordReset.new_token_expiry(hours=24))
            db.session.add(reset)
            db.session.commit()
            link = url_for("auth.reset_password", token=reset.token, _external=True)
            send_email(user, "Welcome to RentalPro", f"An account has been created for you. Set your password: {link}")

        flash("Tenant profile created.", "success")
        if unit_id:
            return redirect(url_for("tenants.upload_lease", tenant_id=tenant.id, unit_id=unit_id))
        return redirect(url_for("tenants.detail", tenant_id=tenant.id))
    return render_template("tenants/add.html", form={}, unit_id=unit_id)


@bp.route("/invite", methods=["GET", "POST"])
@role_required(*MANAGEMENT_ROLES)
def invite():
    from backend.models import TenantInvitation

    unit_id = request.args.get("unit_id") or request.form.get("unit_id")
    unit = Unit.query.get_or_404(unit_id) if unit_id else None
    if unit and unit.status != "VACANT":
        flash("Only vacant units can be invited to.", "error")
        return redirect(url_for("properties.detail", property_id=unit.property_id))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        errors = []
        if not name:
            errors.append("Tenant name is required.")
        if not validate("email", email):
            errors.append("A valid email address is required.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("tenants/invite.html", unit=unit, form=request.form)

        TenantInvitation.query.filter_by(unit_id=unit.id, accepted=False).delete()
        invitation = TenantInvitation(unit_id=unit.id, email=email, name=name, expires_at=TenantInvitation.new_token_expiry(hours=48))
        db.session.add(invitation)
        db.session.commit()
        link = url_for("auth.accept_invitation", token=invitation.token, _external=True)
        send_email_raw(email, "You're invited to RentalPro", f"You've been invited to set up your tenant account: {link}")
        audit_log("tenant_invited", "Unit", unit.id, new_value={"email": email})
        flash(f"Invitation sent to {email} (valid 48 hours).", "success")
        return redirect(url_for("properties.detail", property_id=unit.property_id))
    return render_template("tenants/invite.html", unit=unit, form={})


@bp.route("/<tenant_id>")
@role_required(*MANAGEMENT_ROLES)
def detail(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    leases = tenant.leases.order_by(Lease.start_date.desc()).all()
    vacant_units = Unit.query.filter_by(status="VACANT").all()
    return render_template("tenants/detail.html", tenant=tenant, leases=leases, vacant_units=vacant_units)


@bp.route("/<tenant_id>/upload-lease", methods=["GET", "POST"])
@role_required(*MANAGEMENT_ROLES)
def upload_lease(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    preselect_unit_id = request.args.get("unit_id")
    vacant_units = Unit.query.filter_by(status="VACANT").all()

    if request.method == "POST":
        unit_id = request.form.get("unit_id")
        start_date_raw = request.form.get("start_date")
        end_date_raw = request.form.get("end_date")
        monthly_rent = request.form.get("monthly_rent")
        deposit = request.form.get("deposit") or "0"
        due_day = request.form.get("due_day") or "1"
        lease_file = request.files.get("lease_document")

        errors = []
        unit = db.session.get(Unit, unit_id) if unit_id else None
        if not unit:
            errors.append("Please select a unit.")
        elif unit.active_lease and unit.active_lease.tenant_id != tenant.id:
            errors.append("This unit already has a different active tenant.")
        if not validate("date", start_date_raw):
            errors.append("A valid lease start date is required.")
        if not validate("date", end_date_raw):
            errors.append("A valid lease end date is required.")
        if validate("date", start_date_raw) and validate("date", end_date_raw):
            if date.fromisoformat(end_date_raw) <= date.fromisoformat(start_date_raw):
                errors.append("Lease end date must be after the start date.")
        if not validate("positive_float", monthly_rent):
            errors.append("Monthly rent must be a positive number.")
        if not validate_upload(lease_file, allowed_ext=(".pdf",)):
            errors.append("A signed lease PDF (max 20 MB) is required.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "tenants/upload_lease.html", tenant=tenant, vacant_units=vacant_units, preselect_unit_id=unit_id, form=request.form
            )

        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "leases")
        os.makedirs(upload_dir, exist_ok=True)
        filename = secure_filename(f"{tenant.id}-{secrets.token_hex(6)}.pdf")
        path = os.path.join(upload_dir, filename)
        lease_file.stream.seek(0)
        lease_file.save(path)

        lease = Lease(
            unit_id=unit.id,
            tenant_id=tenant.id,
            start_date=date.fromisoformat(start_date_raw),
            end_date=date.fromisoformat(end_date_raw),
            monthly_rent=float(monthly_rent),
            deposit=float(deposit or 0),
            due_day=max(1, min(31, int(due_day or 1))),
            document_path=path,
        )
        db.session.add(lease)
        unit.status = "OCCUPIED"
        db.session.commit()
        audit_log("lease_uploaded", "Lease", lease.id, new_value={"unit_id": unit.id, "tenant_id": tenant.id})
        send_email(
            tenant.user,
            "Your lease has been activated",
            f"Your lease for unit {unit.unit_code} from {lease.start_date} to {lease.end_date} is now active.",
        )
        flash("Lease activated and unit marked Occupied.", "success")
        return redirect(url_for("tenants.detail", tenant_id=tenant.id))

    return render_template("tenants/upload_lease.html", tenant=tenant, vacant_units=vacant_units, preselect_unit_id=preselect_unit_id, form={})
