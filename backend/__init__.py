import os

from flask import Flask, jsonify, render_template

from backend.config import Config
from backend.extensions import cache, csrf, db, limiter, migrate, scheduler


MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "static"),
    )
    app.config.from_object(config_class)

    from backend.web_security import add_security_headers, check_secret_key

    check_secret_key(app)
    app.after_request(add_security_headers)

    db.init_app(app)
    # render_as_batch lets Alembic alter columns on SQLite, which cannot ALTER in place.
    migrate.init_app(app, db, directory=MIGRATIONS_DIR, render_as_batch=True)
    csrf.init_app(app)
    cache.init_app(app)
    if app.config.get("RATELIMIT_ENABLED", True):
        limiter.init_app(app)
    else:
        limiter.enabled = False

    if app.config.get("STORAGE_BACKEND", "local") == "s3":
        if not app.config.get("S3_BUCKET"):
            raise RuntimeError("STORAGE_BACKEND=s3 needs S3_BUCKET (and AWS credentials) to be set.")
    else:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from backend.routes import ALL_BLUEPRINTS

    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    from backend.i18n import LANGUAGES, current_language, label, ltr, money, text_direction, translate
    from backend.security import current_user, home_url, safe_next_url

    # A Jinja global (not just a context variable) so imported macro files can translate too.
    app.jinja_env.globals["_"] = translate
    app.jinja_env.filters["ltr"] = ltr
    app.jinja_env.filters["label"] = label
    app.jinja_env.filters["money"] = money

    @app.context_processor
    def inject_globals():
        return {
            "current_user": current_user(),
            "home_url": home_url,
            "current_lang": current_language(),
            "text_dir": text_direction(),
            "languages": LANGUAGES,
        }

    @app.route("/lang/<code>")
    def set_language(code):
        from flask import redirect, request, session, url_for

        if code in LANGUAGES:
            session["lang"] = code
            user = current_user()
            if user is not None and user.language != code:
                user.language = code  # emails and SMS follow the user's choice
                db.session.commit()
        return redirect(safe_next_url(request.args.get("next"), url_for("root")))

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def too_many_requests(_e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("errors/500.html"), 500

    @app.route("/")
    def root():
        from flask import redirect, url_for

        return redirect(url_for("auth.login"))

    @app.route("/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
            db_status = "ok"
        except Exception:
            db_status = "error"
        return jsonify({"status": "ok", "db": db_status, "version": "3.1"})

    register_cli(app)

    if app.config.get("SCHEDULER_ENABLED") and not app.config.get("TESTING"):
        register_scheduler(app)

    return app


def register_scheduler(app):
    from backend.scheduler_jobs import (
        job_auto_bill_rent,
        job_escalate_overdue_maintenance,
        job_lease_expiry_alerts,
        job_overdue_alerts,
        job_rent_due_alerts,
    )

    def _wrap(fn):
        def runner():
            with app.app_context():
                fn()

        return runner

    if not scheduler.running:
        scheduler.add_job(_wrap(job_lease_expiry_alerts), "cron", hour=9, minute=0, id="lease_expiry_alerts", replace_existing=True)
        scheduler.add_job(_wrap(job_rent_due_alerts), "cron", hour=8, minute=0, id="rent_due_alerts", replace_existing=True)
        scheduler.add_job(_wrap(job_auto_bill_rent), "cron", hour=8, minute=15, id="auto_bill_rent", replace_existing=True)
        scheduler.add_job(_wrap(job_overdue_alerts), "cron", hour=8, minute=30, id="overdue_alerts", replace_existing=True)
        scheduler.add_job(
            _wrap(job_escalate_overdue_maintenance), "cron", hour=7, minute=0, id="maintenance_escalation", replace_existing=True
        )
        scheduler.start()


# The first migration: the schema db.create_all() used to build before migrations existed.
INITIAL_REVISION = "bcde74b31ea7"


def upgrade_database() -> str:
    """Apply every pending migration. A database built earlier by db.create_all()
    has the tables but no migration record, so it is marked as being at the
    initial revision first instead of having its tables created again."""
    from flask_migrate import stamp, upgrade

    tables = set(db.inspect(db.engine).get_table_names())
    adopted = "users" in tables and "alembic_version" not in tables
    if adopted:
        stamp(directory=MIGRATIONS_DIR, revision=INITIAL_REVISION)
    upgrade(directory=MIGRATIONS_DIR)
    return ("Existing database adopted; " if adopted else "") + "schema is up to date."


def register_cli(app):
    @app.cli.command("create-db")
    def create_db():
        """Create the schema, or bring it up to date, by applying the migrations."""
        print(upgrade_database())

    @app.cli.command("seed-db")
    def seed_db():
        """Populate the database with demo accounts and sample data."""
        from backend.seed import run_seed

        run_seed()
        print("Database seeded.")

    @app.cli.command("run-jobs")
    def run_jobs():
        """Run all five scheduled background jobs once, immediately."""
        from backend.scheduler_jobs import ALL_JOBS

        for job in ALL_JOBS:
            count = job()
            print(f"{job.__name__}: {count} notification(s) dispatched")
