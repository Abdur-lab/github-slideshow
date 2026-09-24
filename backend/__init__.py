import os

from flask import Flask, jsonify, render_template

from backend.config import Config
from backend.extensions import cache, csrf, db, limiter, scheduler


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "static"),
    )
    app.config.from_object(config_class)

    db.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)
    if app.config.get("RATELIMIT_ENABLED", True):
        limiter.init_app(app)
    else:
        limiter.enabled = False

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from backend.routes import ALL_BLUEPRINTS

    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    from backend.security import current_user, home_url

    @app.context_processor
    def inject_globals():
        return {"current_user": current_user(), "home_url": home_url}

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

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


def register_cli(app):
    @app.cli.command("create-db")
    def create_db():
        """Create all tables (dev convenience; use Alembic migrations in production)."""
        db.create_all()
        print("Tables created.")

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
