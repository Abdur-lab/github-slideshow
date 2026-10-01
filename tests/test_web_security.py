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
