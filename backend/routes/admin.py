"""Admin user & role management (UC-02) and staff account creation
(FR-044). Role changes and activation toggles are ADMIN-only; creating a
Maintenance Staff account is also available to Owner/Manager, mirroring
how tenant accounts are created in tenants.py."""
import secrets

from flask import Blueprint, flash, redirect, render_template, request, url_for

from backend.extensions import db
from backend.models import ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER, ROLE_STAFF, ROLES, PasswordReset, User
from backend.security import audit_log, current_user, role_required, validate
from backend.services.notifications import send_email

MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/users")
@role_required(ROLE_ADMIN)
def users():
    all_users = User.query.order_by(User.role, User.last_name, User.first_name).all()
    return render_template("admin/users.html", users=all_users, roles=ROLES)


@bp.route("/users/<user_id>/edit", methods=["POST"])
@role_required(ROLE_ADMIN)
def edit_user(user_id):
    target = User.query.get_or_404(user_id)
    new_role = request.form.get("role", target.role)
    new_active = request.form.get("is_active") == "on"

    if new_role not in ROLES:
        flash("Invalid role.", "error")
        return redirect(url_for("admin.users"))

    would_remove_last_owner = (
        (target.role == ROLE_OWNER and new_role != ROLE_OWNER)
        or (target.role == ROLE_OWNER and not new_active)
    )
    if would_remove_last_owner:
        remaining_owners = User.query.filter(User.role == ROLE_OWNER, User.is_active.is_(True), User.id != target.id).count()
        if remaining_owners == 0:
            flash("Every account must have at least one active Property Owner. This change was blocked.", "error")
            return redirect(url_for("admin.users"))

    old_role, old_active = target.role, target.is_active
    target.role = new_role
    target.is_active = new_active
    db.session.commit()
    audit_log(
        "user_role_changed",
        "User",
        target.id,
        old_value={"role": old_role, "is_active": old_active},
        new_value={"role": new_role, "is_active": new_active},
    )
    send_email(target, "Your RentalPro account was updated", f"Your account role is now {new_role.replace('_', ' ').title()}.")
    flash(f"Updated {target.full_name}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/staff/add", methods=["GET", "POST"])
@role_required(*MANAGEMENT_ROLES)
def add_staff():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not validate("email", email):
            errors.append("A valid email address is required.")
        elif User.query.filter_by(email=email).first():
            errors.append("A user with this email already exists.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/add_staff.html", form=request.form)

        first_name, _, last_name = full_name.partition(" ")
        user = User(email=email, first_name=first_name or full_name, last_name=last_name or "-", role=ROLE_STAFF)
        user.set_password(secrets.token_urlsafe(16))
        db.session.add(user)
        db.session.flush()
        reset = PasswordReset(user_id=user.id, expires_at=PasswordReset.new_token_expiry(hours=24))
        db.session.add(reset)
        db.session.commit()
        audit_log("staff_created", "User", user.id, new_value={"email": email})

        link = url_for("auth.reset_password", token=reset.token, _external=True)
        send_email(user, "Welcome to RentalPro", f"A Maintenance Staff account has been created for you. Set your password: {link}")

        flash(f"Staff account created for {user.full_name}.", "success")
        return redirect(url_for("admin.users") if current_user().role == ROLE_ADMIN else url_for("maintenance.index"))
    return render_template("admin/add_staff.html", form={})
