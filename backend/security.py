"""Auth, RBAC, IDOR protection, input validation, and audit logging helpers."""
import os
import re
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import abort, g, has_request_context, redirect, request, session, url_for

from backend.extensions import db
from backend.models import AuditLog, Property, ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER, User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


# --- Session / current user ---------------------------------------------------

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    cached = getattr(g, "_current_user", None)
    if cached is not None and cached.id == uid:
        return cached
    user = db.session.get(User, uid)
    g._current_user = user
    return user


def login_user(user: User) -> None:
    session.clear()
    session["user_id"] = user.id
    session.permanent = True


def logout_user() -> None:
    session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = current_user()
            if user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def safe_next_url(next_url: str, default: str) -> str:
    """Blocks open-redirect (//evil.com or scheme-qualified) 'next' params."""
    if not next_url:
        return default
    parsed = urlparse(next_url)
    if parsed.netloc or parsed.scheme:
        return default
    return next_url


# --- IDOR protection ------------------------------------------------------------

def assert_owner(property_id: str) -> None:
    """Verifies the current user may access the given property in a single
    EXISTS-style query (not one query per candidate condition)."""
    user = current_user()
    if user is None:
        abort(403)
    if user.role in (ROLE_ADMIN, ROLE_MANAGER):
        allowed = db.session.query(Property.id).filter(Property.id == property_id).scalar() is not None
    elif user.role == ROLE_OWNER:
        allowed = (
            db.session.query(Property.id)
            .filter(Property.id == property_id, Property.owner_id == user.id)
            .scalar()
            is not None
        )
    else:
        allowed = False
    if not allowed:
        abort(403)


def assert_tenant_self(tenant_id: str) -> None:
    """Tenants may only access their own records; staff roles bypass."""
    user = current_user()
    if user is None:
        abort(403)
    if user.role in (ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER):
        return
    if user.role == "TENANT" and user.tenant_profile and user.tenant_profile.id == tenant_id:
        return
    abort(403)


# --- Validation -------------------------------------------------------------

def validate(kind: str, value) -> bool:
    """Named-kind validator: positive_float, positive_int, email, date, min8, max200."""
    if kind == "positive_float":
        try:
            return float(value) > 0
        except (TypeError, ValueError):
            return False
    if kind == "positive_int":
        try:
            return int(value) > 0
        except (TypeError, ValueError):
            return False
    if kind == "email":
        return bool(value) and bool(EMAIL_RE.match(value))
    if kind == "date":
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True
        except (TypeError, ValueError):
            return False
    if kind == "min8":
        return bool(value) and len(value) >= 8
    if kind == "max200":
        return bool(value) and len(value) <= 200
    raise ValueError(f"Unknown validation kind: {kind}")


IMAGE_MAGIC = {
    b"\xff\xd8\xff": (".jpg", ".jpeg"),
    b"\x89PNG\r\n\x1a\n": (".png",),
}


def validate_upload(file_storage, allowed_ext=(".pdf",), max_bytes: int = 20 * 1024 * 1024) -> bool:
    """Rejects missing files, wrong extensions, oversized files, and content
    that doesn't match its claimed type (checked via magic bytes for PDF
    and, when an image extension is allowed, for JPEG/PNG too)."""
    if file_storage is None or not getattr(file_storage, "filename", None):
        return False
    filename = file_storage.filename
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_ext:
        return False

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0 or size > max_bytes:
        return False

    head = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    if not head:
        return False
    if ext == ".pdf":
        return head[:5] == b"%PDF-"
    if ext in (".jpg", ".jpeg"):
        return head[:3] == b"\xff\xd8\xff"
    if ext == ".png":
        return head[:8] == b"\x89PNG\r\n\x1a\n"
    return True


# --- Audit log ----------------------------------------------------------------

def audit_log(action: str, entity_type: str, entity_id: str = None, old_value=None, new_value=None, user_id=None):
    """Writes an immutable audit entry. Safe to call outside a request
    context (e.g. from a scheduler job), where ip_address is 'scheduler'."""
    if has_request_context():
        ip = request.remote_addr
        if user_id is None:
            user_id = session.get("user_id")
    else:
        ip = "scheduler"
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def register_login_failure(user: User) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
    db.session.commit()


def clear_login_failures(user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.session.commit()
