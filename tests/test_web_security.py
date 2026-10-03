import pathlib
import re

import pytest

from backend import create_app
from backend.config import TestConfig
from tests.conftest import login

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "templates"


def _config(**overrides):
    return type("ProdLikeConfig", (TestConfig,), {"TESTING": False, **overrides})


@pytest.mark.parametrize("key", [None, "", "dev-only-insecure-key-change-me", "change-me-in-production"])
def test_app_refuses_to_start_without_a_real_secret_key(monkeypatch, key):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(_config(SECRET_KEY=key))


def test_debug_mode_gets_a_random_key_instead_of_a_known_one(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "1")
    first = create_app(_config(SECRET_KEY=None)).config["SECRET_KEY"]
    second = create_app(_config(SECRET_KEY=None)).config["SECRET_KEY"]
    assert len(first) == 64 and first != second


def test_a_real_secret_key_is_kept(monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    key = "a" * 64
    assert create_app(_config(SECRET_KEY=key)).config["SECRET_KEY"] == key


def test_every_response_carries_security_headers(client):
    headers = client.get("/login").headers
    csp = headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "'unsafe-inline'" not in csp
    assert "frame-ancestors 'none'" in csp
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" not in headers  # only sent over HTTPS


def test_hsts_is_sent_over_https(client):
    assert "max-age=" in client.get("/login", base_url="https://localhost").headers["Strict-Transport-Security"]


def test_session_cookie_is_http_only_and_same_site(client, owner):
    resp = client.post("/login", data={"email": owner.email, "password": "password123"})
    cookie = resp.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_session_cookie_is_https_only_when_configured():
    app = create_app(type("SecureCookies", (TestConfig,), {"SESSION_COOKIE_SECURE": True}))
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_templates_have_no_inline_scripts_handlers_or_styles():
    """The Content-Security-Policy blocks these, so they would silently stop working."""
    offenders = []
    for path in TEMPLATES.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"<script>|<script(?![^>]*\bsrc=)(?![^>]*application/json)[^>]*>", text):
            offenders.append(f"{path.name}: inline <script>")
        if re.search(r"\son[a-z]+=\"", text):
            offenders.append(f"{path.name}: inline event handler")
        if re.search(r"\sstyle=\"|<style", text):
            offenders.append(f"{path.name}: inline style")
    assert not offenders


def test_destructive_actions_still_ask_for_confirmation(client, owner, property_):
    login(client, owner.email)
    page = client.get(f"/properties/{property_.id}").get_data(as_text=True)
    assert 'data-confirm="Archive this property?"' in page
    assert "js/app.js" in page


def test_rate_limit_page_is_translated():
    from backend.extensions import db, limiter

    app = create_app(type("RateLimited", (TestConfig,), {"RATELIMIT_ENABLED": True}))
    limiter.enabled = True
    with app.app_context():
        db.create_all()
    client = app.test_client()
    client.get("/lang/ar")
    try:
        for _ in range(11):
            resp = client.post("/login", data={"email": "nobody@test.com", "password": "x"})
    finally:
        limiter.reset()
    assert resp.status_code == 429
    page = resp.get_data(as_text=True)
    assert "محاولات كثيرة جدًا" in page and 'dir="rtl"' in page
    assert "Too Many Requests" not in page


def test_https_is_recognised_behind_a_proxy():
    """Render and similar hosts end HTTPS at their proxy and reach the app over HTTP."""
    from backend.extensions import db
    from backend.models import ROLE_OWNER, Notification
    from tests.conftest import make_user

    app = create_app(type("BehindProxy", (TestConfig,), {"TRUST_FORWARDED_PROTO": True}))
    with app.app_context():
        db.create_all()
        user = make_user(db, "owner@test.com", ROLE_OWNER)
        resp = app.test_client().post(
            "/forgot-password", data={"email": user.email}, headers={"X-Forwarded-Proto": "https"}
        )
        assert "max-age=" in resp.headers["Strict-Transport-Security"]
        assert "https://localhost/reset-password/" in Notification.query.one().body


def test_forwarded_proto_is_ignored_unless_configured(client):
    resp = client.get("/login", headers={"X-Forwarded-Proto": "https"})
    assert "Strict-Transport-Security" not in resp.headers


@pytest.mark.parametrize(
    "client_ip_header, second_visitor_limited",
    [
        ("True-Client-IP", False),  # behind the proxy: each visitor has their own limit
        ("", True),  # reached directly: a forged header does not escape the limit
    ],
)
def test_login_rate_limit_is_per_visitor_behind_a_proxy(client_ip_header, second_visitor_limited):
    from backend.extensions import db, limiter

    config = {"RATELIMIT_ENABLED": True, "CLIENT_IP_HEADER": client_ip_header}
    app = create_app(type("BehindProxy", (TestConfig,), config))
    limiter.enabled = True
    with app.app_context():
        db.create_all()
    client = app.test_client()

    def attempt(ip):
        return client.post("/login", data={"email": "nobody@test.com", "password": "x"}, headers={"True-Client-IP": ip})

    try:
        for _ in range(10):
            attempt("203.0.113.1")
        assert attempt("203.0.113.1").status_code == 429
        assert (attempt("203.0.113.2").status_code == 429) is second_visitor_limited
    finally:
        limiter.reset()


def test_a_malformed_client_ip_header_keeps_the_connecting_address():
    from backend.extensions import db
    from backend.models import AuditLog
    from backend.security import audit_log

    app = create_app(type("BehindProxy", (TestConfig,), {"CLIENT_IP_HEADER": "True-Client-IP"}))
    with app.app_context():
        db.create_all()

    @app.route("/_audit")
    def _audit():
        return audit_log("probe", "Test").ip_address

    client = app.test_client()
    assert client.get("/_audit", headers={"True-Client-IP": " 2001:db8::1 "}).text == "2001:db8::1"
    assert client.get("/_audit", headers={"True-Client-IP": "not-an-ip"}).text == "127.0.0.1"
    with app.app_context():
        assert AuditLog.query.count() == 2
