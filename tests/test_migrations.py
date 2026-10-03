import pathlib

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade

from backend import INITIAL_REVISION, MIGRATIONS_DIR, create_app, upgrade_database
from backend.config import TestConfig, database_url
from backend.extensions import db
from backend.models import ROLE_OWNER, User


def _app(tmp_path):
    uri = f"sqlite:///{tmp_path / 'rentalpro.db'}"
    return create_app(type("FileDbConfig", (TestConfig,), {"SQLALCHEMY_DATABASE_URI": uri}))


def _revision():
    return db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalar()


def test_migrations_build_exactly_the_schema_the_models_describe(tmp_path):
    """Fails when a model changes without a matching migration (run `flask db migrate`)."""
    app = _app(tmp_path)
    with app.app_context():
        assert upgrade_database() == "schema is up to date."
        with db.engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), db.metadata)
        assert diff == []


def test_a_database_made_by_create_all_is_adopted_without_losing_data(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        # A database from before migrations existed: the original tables, built by
        # db.create_all(), with no alembic_version record.
        upgrade(directory=MIGRATIONS_DIR, revision=INITIAL_REVISION)
        db.session.execute(db.text("DROP TABLE alembic_version"))
        db.session.execute(db.text(
            "INSERT INTO users (id, email, password_hash, first_name, last_name, role, is_active, "
            "failed_login_attempts, opt_out_sms, opt_out_email, created_at) VALUES "
            "('u1', 'kept@test.com', 'x', 'Kept', 'User', :role, 1, 0, 0, 0, '2026-01-01')"
        ), {"role": ROLE_OWNER})
        db.session.commit()

        assert upgrade_database().startswith("Existing database adopted")
        assert _revision() is not None
        kept = User.query.filter_by(email="kept@test.com").one()
        assert kept.language == "en"  # added by a later migration, with its default

        assert upgrade_database() == "schema is up to date."  # running it again is harmless


def test_migrations_can_be_rolled_back_and_reapplied(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        upgrade_database()
        head = _revision()
        downgrade(directory=MIGRATIONS_DIR, revision="base")
        assert "users" not in db.inspect(db.engine).get_table_names()
        upgrade_database()
        assert _revision() == head


def test_the_initial_revision_constant_names_the_first_migration():
    versions = pathlib.Path(MIGRATIONS_DIR) / "versions"
    first = [p for p in versions.glob("*.py") if "down_revision = None" in p.read_text()]
    assert len(first) == 1 and f"revision = '{INITIAL_REVISION}'" in first[0].read_text()


def test_postgres_urls_use_the_installed_driver():
    """Render and Heroku hand out postgres://, which SQLAlchemy 2 rejects, and SQLAlchemy 2.1
    defaults postgresql:// to psycopg 3, which is not installed."""
    from sqlalchemy.engine import make_url

    for url in ("postgres://u:p@host/db", "postgresql://u:p@host/db"):
        assert make_url(database_url(url)).get_dialect().driver == "psycopg2"
    assert database_url("postgresql+psycopg2://u:p@host/db") == "postgresql+psycopg2://u:p@host/db"
    assert database_url("sqlite:///rentalpro.db") == "sqlite:///rentalpro.db"
