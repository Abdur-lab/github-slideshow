import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///rentalpro.db")
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

    SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "true").lower() == "true"
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "true").lower() == "true"

    WTF_CSRF_TIME_LIMIT = None


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SCHEDULER_ENABLED = False
    RATELIMIT_ENABLED = False
    CACHE_TYPE = "SimpleCache"
    SECRET_KEY = "test-secret-key"
