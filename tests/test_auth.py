import pytest

from backend.models import Property
from tests.conftest import login


def test_login_success_redirects_by_role(client, owner, manager, staff, tenant):
    resp = login(client, "owner@test.com")
    assert resp.status_code == 200
    assert b"Portfolio Dashboard" in resp.data

    resp = login(client, "tenant@test.com")
    assert resp.status_code == 200
    assert b"Welcome" in resp.data

    resp = login(client, "staff@test.com")
    assert resp.status_code == 200
    assert b"My Work Queue" in resp.data


def test_sidebar_brand_links_to_each_roles_home(client, owner, staff, tenant):
    login(client, "owner@test.com")
    assert b'href="/dashboard" class="brand"' in client.get("/properties").data

    login(client, "staff@test.com")
    assert b'href="/maintenance" class="brand"' in client.get("/maintenance").data

    login(client, "tenant@test.com")
    assert b'href="/portal" class="brand"' in client.get("/portal").data


@pytest.mark.parametrize("path", ["/", "/login", "/forgot-password"])
def test_logged_in_user_is_sent_home_from_logged_out_pages(client, owner, tenant, path):
    login(client, "owner@test.com")
    resp = client.get(path, follow_redirects=True)
    assert b"Portfolio Dashboard" in resp.data

    login(client, "tenant@test.com")
    resp = client.get(path, follow_redirects=True)
    assert b"Welcome" in resp.data


def test_login_page_still_shows_when_logged_out(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Log in" in resp.data


def test_login_wrong_password(client, owner):
    resp = client.post("/login", data={"email": "owner@test.com", "password": "not-the-password"}, follow_redirects=True)
    assert b"Invalid email or password" in resp.data


def test_login_nonexistent_email(client):
    resp = client.post("/login", data={"email": "ghost@test.com", "password": "whatever"}, follow_redirects=True)
    assert b"Invalid email or password" in resp.data


def test_account_lockout_after_five_failures(client, owner):
    for _ in range(5):
        client.post("/login", data={"email": "owner@test.com", "password": "wrong"})
    resp = client.post("/login", data={"email": "owner@test.com", "password": "password123"}, follow_redirects=True)
    assert b"Account locked" in resp.data


MANAGEMENT_ROUTES = ["/dashboard", "/properties", "/tenants", "/rent", "/reports"]


@pytest.mark.parametrize("role_fixture", ["owner", "manager"])
def test_management_roles_can_access_management_routes(client, request, role_fixture):
    user = request.getfixturevalue(role_fixture)
    login(client, user.email)
    for route in MANAGEMENT_ROUTES:
        resp = client.get(route)
        assert resp.status_code == 200, f"{route} should be 200 for {role_fixture}"


def test_staff_blocked_from_management_routes(client, staff):
    login(client, staff.email)
    for route in MANAGEMENT_ROUTES:
        resp = client.get(route)
        assert resp.status_code == 403, f"{route} should be 403 for staff"
    assert client.get("/maintenance").status_code == 200


def test_tenant_blocked_from_management_routes(client, tenant):
    login(client, tenant.user.email)
    for route in MANAGEMENT_ROUTES:
        resp = client.get(route)
        assert resp.status_code == 403, f"{route} should be 403 for tenant"
    assert client.get("/portal").status_code == 200


def test_manager_cannot_create_property(client, manager):
    login(client, manager.email)
    resp = client.get("/properties/add")
    assert resp.status_code == 403


def test_owner_can_create_property(client, owner):
    login(client, owner.email)
    resp = client.get("/properties/add")
    assert resp.status_code == 200


def test_idor_second_owner_cannot_view_first_owner_property(client, db, owner, property_):
    from backend.models import ROLE_OWNER, User

    second_owner = User(email="owner2@test.com", first_name="Sec", last_name="Ond", role=ROLE_OWNER)
    second_owner.set_password("password123")
    db.session.add(second_owner)
    db.session.commit()

    login(client, "owner2@test.com")
    resp = client.get(f"/properties/{property_.id}")
    assert resp.status_code == 403


def test_admin_bypasses_ownership_check(client, admin, property_):
    login(client, admin.email)
    resp = client.get(f"/properties/{property_.id}")
    assert resp.status_code == 200


def test_manager_can_view_any_owners_property(client, manager, property_):
    login(client, manager.email)
    resp = client.get(f"/properties/{property_.id}")
    assert resp.status_code == 200


def test_logout_clears_session(client, owner):
    login(client, owner.email)
    assert client.get("/dashboard").status_code == 200
    client.get("/logout")
    resp = client.get("/dashboard", follow_redirects=True)
    assert b"RentalPro" in resp.data and b"Portfolio Dashboard" not in resp.data
