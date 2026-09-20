from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from backend.extensions import db, limiter
from backend.models import ROLE_TENANT, PasswordReset, Tenant, TenantInvitation, User
from backend.security import (
    audit_log,
    clear_login_failures,
    current_user,
    login_user,
    logout_user,
    register_login_failure,
    safe_next_url,
    validate,
)
from backend.services.notifications import send_email

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user is None or not user.is_active:
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html")
        if user.is_locked():
            flash("Account locked due to too many failed attempts. Try again in 15 minutes.", "error")
            return render_template("auth/login.html")
        if not user.check_password(password):
            register_login_failure(user)
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html")
        clear_login_failures(user)
        login_user(user)
        audit_log("login", "User", user.id)
        default = url_for("portal.index") if user.role == ROLE_TENANT else url_for("dashboard.index")
        return redirect(safe_next_url(request.args.get("next") or request.form.get("next"), default))
    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    user = current_user()
    if user:
        audit_log("logout", "User", user.id)
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            reset = PasswordReset(user_id=user.id, expires_at=PasswordReset.new_token_expiry(hours=1))
            db.session.add(reset)
            db.session.commit()
            link = url_for("auth.reset_password", token=reset.token, _external=True)
            send_email(user, "Reset your RentalPro password", f"Reset your password (valid 1 hour): {link}")
        flash("If that email exists, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    reset = PasswordReset.query.filter_by(token=token).first()
    if not reset or not reset.is_valid:
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if not validate("min8", password):
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/reset_password.html", token=token)
        user = db.session.get(User, reset.user_id)
        user.set_password(password)
        reset.used = True
        db.session.commit()
        audit_log("password_reset", "User", user.id)
        flash("Password updated. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", token=token)


@bp.route("/register/invitation/<token>", methods=["GET", "POST"])
def accept_invitation(token):
    invitation = TenantInvitation.query.filter_by(token=token).first()
    if not invitation or not invitation.is_valid:
        flash("This invitation is invalid or has expired.", "error")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        national_id = request.form.get("national_id", "").strip()
        phone = request.form.get("phone", "").strip()
        emergency_contact = request.form.get("emergency_contact", "").strip()
        password = request.form.get("password", "")
        errors = []
        if not validate("min8", password):
            errors.append("Password must be at least 8 characters.")
        if not national_id:
            errors.append("National ID is required.")
        if User.query.filter_by(email=invitation.email).first():
            errors.append("An account with this email already exists. Please log in instead.")
        if Tenant.query.filter_by(national_id=national_id).first():
            errors.append("A tenant with this national ID already exists.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/accept_invitation.html", invitation=invitation)

        first_name, _, last_name = invitation.name.partition(" ")
        user = User(email=invitation.email, first_name=first_name or invitation.name, last_name=last_name or "-", role=ROLE_TENANT)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        tenant = Tenant(user_id=user.id, national_id=national_id, phone=phone, emergency_contact=emergency_contact)
        db.session.add(tenant)
        invitation.accepted = True
        db.session.commit()
        audit_log("tenant_self_registered", "Tenant", tenant.id)
        login_user(user)
        flash("Welcome to RentalPro! Your profile has been created.", "success")
        return redirect(url_for("portal.index"))
    return render_template("auth/accept_invitation.html", invitation=invitation)
