"""Start-up and response hardening: a real secret key and standard security headers."""
import os
import secrets

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
