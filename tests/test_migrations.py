import pathlib

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade

from backend import INITIAL_REVISION, MIGRATIONS_DIR, create_app, upgrade_database
from backend.config import TestConfig
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
        db.create_all()  # how databases were built before migrations existed
        user = User(email="kept@test.com", first_name="Kept", last_name="User", role=ROLE_OWNER)
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        assert upgrade_database().startswith("Existing database adopted")
        assert _revision() is not None
        assert User.query.filter_by(email="kept@test.com").one()

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
