from datetime import date, timedelta

import pytest

from backend import create_app
from backend.config import TestConfig
from backend.extensions import db as _db
from backend.models import (
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_OWNER,
    ROLE_STAFF,
    ROLE_TENANT,
    Lease,
    Property,
    Tenant,
    Unit,
    User,
)

DEFAULT_PASSWORD = "password123"


@pytest.fixture()
def app():
    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(db, email, role, password=DEFAULT_PASSWORD, first="Test", last="User"):
    user = User(email=email, first_name=first, last_name=last, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def admin(db):
    return make_user(db, "admin@test.com", ROLE_ADMIN, first="Ada", last="Admin")


@pytest.fixture()
def owner(db):
    return make_user(db, "owner@test.com", ROLE_OWNER, first="Olivia", last="Owner")


@pytest.fixture()
def manager(db):
    return make_user(db, "manager@test.com", ROLE_MANAGER, first="Marco", last="Manager")


@pytest.fixture()
def staff(db):
    return make_user(db, "staff@test.com", ROLE_STAFF, first="Sam", last="Staff")


@pytest.fixture()
def tenant(db):
    user = make_user(db, "tenant@test.com", ROLE_TENANT, first="Tara", last="Tenant")
    t = Tenant(user_id=user.id, national_id="ID-0001", phone="555-0000", emergency_contact="Emg Contact 555-1111")
    db.session.add(t)
    db.session.commit()
    return t


@pytest.fixture()
def property_(db, owner):
    p = Property(
        owner_id=owner.id,
        name="Test Towers",
        address="1 Main St",
        city="Testville",
        country="Testland",
        property_code=Property.generate_property_code(),
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture()
def unit(db, property_):
    u = Unit(
        property_id=property_.id,
        unit_number="101",
        monthly_rent=1000.0,
        deposit=1000.0,
        unit_code=Unit.generate_unit_code(property_.property_code, "101"),
    )
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def active_lease(db, unit, tenant):
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=date.today() - timedelta(days=40),
        end_date=date.today() + timedelta(days=325),
        monthly_rent=unit.monthly_rent,
        deposit=unit.deposit,
        due_day=1,
    )
    unit.status = "OCCUPIED"
    db.session.add(lease)
    db.session.commit()
    return lease


def login(client, email, password=DEFAULT_PASSWORD):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)
