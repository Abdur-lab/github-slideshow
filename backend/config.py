import os


def database_url(url: str) -> str:
    """Name the PostgreSQL driver this project installs (psycopg2-binary): SQLAlchemy 2.1
    otherwise picks psycopg 3. Also accepts the postgres:// URLs Render and Heroku hand
    out, a scheme SQLAlchemy 2 no longer recognises."""
    for scheme in ("postgres://", "postgresql://"):
        if url.startswith(scheme):
            return "postgresql+psycopg2://" + url[len(scheme):]
    return url


class Config:
    # No fallback: create_app refuses to start without a real key (see check_secret_key).
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = database_url(os.environ.get("DATABASE_URL", "sqlite:///rentalpro.db"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = os.environ.get("REDIS_URL", "memory://")
    CACHE_TYPE = "RedisCache" if os.environ.get("REDIS_URL") else "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 60
    CACHE_REDIS_URL = os.environ.get("REDIS_URL")

    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB uploads
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
    # "local" keeps uploads in UPLOAD_FOLDER; "s3" keeps them in an S3-compatible
    # bucket (set S3_ENDPOINT_URL for R2, MinIO, etc.). See services/storage.py.
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").lower()
    S3_BUCKET = os.environ.get("S3_BUCKET")
    S3_REGION = os.environ.get("S3_REGION")
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
    S3_PREFIX = os.environ.get("S3_PREFIX", "")

    SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "true").lower() == "true"
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "true").lower() == "true"

    WTF_CSRF_TIME_LIMIT = None

    # Session cookie: never readable from JavaScript, not sent on cross-site
    # form posts, and HTTPS-only when SESSION_COOKIE_SECURE=true (set it in
    # production; leave it off for http://localhost development).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # Behind a hosting platform's proxy (Render, Railway, ...) every request arrives
    # from the proxy; see web_security.trust_proxy_headers. Leave both unset when
    # visitors reach the app directly, or they could forge these headers.
    CLIENT_IP_HEADER = os.environ.get("CLIENT_IP_HEADER", "")
    TRUST_FORWARDED_PROTO = os.environ.get("TRUST_FORWARDED_PROTO", "false").lower() == "true"


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SCHEDULER_ENABLED = False
    RATELIMIT_ENABLED = False
    CACHE_TYPE = "SimpleCache"
    SECRET_KEY = "test-secret-key"
