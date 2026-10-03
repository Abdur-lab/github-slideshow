"""Start-up and response hardening: a real secret key, standard security headers,
and the visitor's real address and scheme when running behind a proxy."""
import ipaddress
import os
import secrets

from werkzeug.middleware.proxy_fix import ProxyFix

# Placeholder values that have appeared in this project's config and docs.
INSECURE_SECRET_KEYS = {
    "",
    "dev-only-insecure-key-change-me",
    "change-me-in-production",
    "change-me-to-a-random-value",
}

# Scripts and styles come only from this site (Leaflet is vendored), map tiles
# from OpenStreetMap, and the pay form may hand off to Stripe Checkout.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data: https://*.tile.openstreetmap.org",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "form-action 'self' https://checkout.stripe.com",
    ]
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def check_secret_key(app) -> None:
    """Refuse to run with a missing or publicly known SECRET_KEY, which would let
    anyone forge a session cookie and log in as any user.

    In debug mode (FLASK_DEBUG=1) a random key is generated instead, so local
    development still works; sessions then end when the server restarts.
    """
    if app.config.get("TESTING"):
        return
    if (app.config.get("SECRET_KEY") or "") not in INSECURE_SECRET_KEYS:
        return
    if app.debug or os.environ.get("FLASK_DEBUG") == "1":
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning("SECRET_KEY is not set; using a random key for this debug run only.")
        return
    raise RuntimeError(
        "SECRET_KEY is missing or is a published placeholder. Set it to a long random value, e.g. "
        "export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')"
    )


def add_security_headers(response):
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    from flask import request

    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def trust_proxy_headers(app) -> None:
    """On a hosting platform every request reaches the app from the platform's proxy,
    over plain HTTP. Without this, all visitors share the proxy's address (and so one
    login rate limit), HSTS is never sent, and emailed reset and invitation links
    start with http://. Both settings are off unless configured, because a visitor
    who reaches the app directly could forge these headers.

    CLIENT_IP_HEADER names a header the proxy overwrites with the visitor's address
    (True-Client-IP on Render, CF-Connecting-IP behind Cloudflare). It becomes
    request.remote_addr, which the rate limiter and the audit log use.
    TRUST_FORWARDED_PROTO=true takes the scheme from the proxy's X-Forwarded-Proto.
    """
    if app.config.get("TRUST_FORWARDED_PROTO"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=1)
    header = app.config.get("CLIENT_IP_HEADER")
    if header:
        app.wsgi_app = _client_ip_from_header(app.wsgi_app, header)


def _client_ip_from_header(wsgi_app, header: str):
    key = "HTTP_" + header.upper().replace("-", "_")

    def middleware(environ, start_response):
        value = environ.get(key, "").strip()
        try:
            environ["REMOTE_ADDR"] = str(ipaddress.ip_address(value))
        except ValueError:
            pass  # missing or malformed: keep the connecting address
        return wsgi_app(environ, start_response)

    return middleware
