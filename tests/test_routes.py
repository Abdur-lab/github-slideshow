import io
from datetime import date, timedelta

from backend.models import (
    Lease,
    MaintenanceRequest,
    Property,
    RentPayment,
    Tenant,
    TenantInvitation,
    Unit,
    User,
)
from tests.conftest import login

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def test_add_property_generates_code(client, db, owner):
    login(client, owner.email)
    resp = client.post(
        "/properties/add",
        data={"name": "New Villas", "address": "9 Sea Rd", "city": "Testville", "country": "Testland", "type": "RESIDENTIAL", "currency": "USD"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    prop = Property.query.filter_by(name="New Villas").first()
    assert prop is not None
    assert prop.property_code.startswith("PROP-")


def test_add_unit_generates_code_and_vacant_status(client, db, owner, property_):
    login(client, owner.email)
    resp = client.post(
        f"/properties/{property_.id}/add-unit",
        data={"unit_number": "201", "type": "STUDIO", "monthly_rent": "900"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    unit = Unit.query.filter_by(property_id=property_.id, unit_number="201").first()
    assert unit is not None
    assert unit.status == "VACANT"
    assert "-U" in unit.unit_code


def test_archive_unit_blocked_by_active_lease(client, db, owner, active_lease, unit, property_):
    login(client, owner.email)
    resp = client.post(f"/properties/{property_.id}/units/{unit.id}/archive", follow_redirects=True)
    assert b"active lease" in resp.data
    db.session.refresh(unit)
    assert unit.status != "ARCHIVED"


def test_archive_unit_allowed_when_vacant(client, db, owner, property_, unit):
    login(client, owner.email)
    resp = client.post(f"/properties/{property_.id}/units/{unit.id}/archive", follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(unit)
    assert unit.status == "ARCHIVED"


def test_add_tenant_creates_user_and_tenant(client, db, manager):
    login(client, manager.email)
    resp = client.post(
        "/tenants/add",
        data={"full_name": "New Tenant", "national_id": "ID-NEW-1", "email": "newtenant@test.com", "phone": "555"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    t = Tenant.query.filter_by(national_id="ID-NEW-1").first()
    assert t is not None
    assert t.user.email == "newtenant@test.com"


def test_invite_tenant_sets_48_hour_expiry(client, db, manager, unit):
    login(client, manager.email)
    resp = client.post("/tenants/invite", data={"unit_id": unit.id, "name": "Invited One", "email": "invited@test.com"}, follow_redirects=True)
    assert resp.status_code == 200
    invitation = TenantInvitation.query.filter_by(email="invited@test.com").first()
    assert invitation is not None
    delta = invitation.expires_at - invitation.created_at
    assert timedelta(hours=47, minutes=55) < delta < timedelta(hours=48, minutes=5)


def test_accept_invitation_creates_tenant_and_logs_in(client, db, manager, unit):
    login(client, manager.email)
    client.post("/tenants/invite", data={"unit_id": unit.id, "name": "Invited Two", "email": "invited2@test.com"})
    invitation = TenantInvitation.query.filter_by(email="invited2@test.com").first()
    client.get("/logout")

    resp = client.post(
        f"/register/invitation/{invitation.token}",
        data={"national_id": "ID-INV-2", "phone": "555", "emergency_contact": "x", "password": "password123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Welcome, Invited" in resp.data
    tenant = Tenant.query.filter_by(national_id="ID-INV-2").first()
    assert tenant is not None
    assert tenant.user.email == "invited2@test.com"


def test_upload_lease_sets_unit_occupied(client, db, manager, tenant, unit):
    login(client, manager.email)
    data = {
        "unit_id": unit.id,
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=365)),
        "monthly_rent": "1000",
        "deposit": "1000",
        "due_day": "1",
        "lease_document": (io.BytesIO(MINIMAL_PDF), "lease.pdf"),
    }
    resp = client.post(f"/tenants/{tenant.id}/upload-lease", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(unit)
    assert unit.status == "OCCUPIED"
    lease = Lease.query.filter_by(unit_id=unit.id, tenant_id=tenant.id).first()
    assert lease is not None


def test_upload_lease_rejects_non_pdf(client, db, manager, tenant, unit):
    login(client, manager.email)
    data = {
        "unit_id": unit.id,
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=365)),
        "monthly_rent": "1000",
        "lease_document": (io.BytesIO(b"not a pdf"), "lease.pdf"),
    }
    resp = client.post(f"/tenants/{tenant.id}/upload-lease", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert b"signed lease PDF" in resp.data
    db.session.refresh(unit)
    assert unit.status == "VACANT"


def test_record_payment_generates_receipt_and_updates_balance(client, db, manager, active_lease):
    login(client, manager.email)
    balance_before = active_lease.balance
    resp = client.post(
        "/rent/record", data={"lease_id": active_lease.id, "amount": "500", "method": "CASH"}, follow_redirects=True
    )
    assert resp.status_code == 200
    payment = RentPayment.query.filter_by(lease_id=active_lease.id).first()
    assert payment is not None
    assert payment.receipt_number.startswith("RCP-")
    db.session.refresh(active_lease)
    assert active_lease.balance == max(0.0, round(balance_before - 500, 2))


def test_pay_rent_online_dev_mode_end_to_end(client, db, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.post("/portal/pay", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Payment successful" in resp.data
    payment = RentPayment.query.filter_by(lease_id=active_lease.id, method="ONLINE").first()
    assert payment is not None


def test_lease_statement_api_blocked_for_wrong_tenant(client, db, active_lease):
    from backend.models import ROLE_TENANT

    other_user = User(email="othertenant@test.com", first_name="Other", last_name="Tenant", role=ROLE_TENANT)
    other_user.set_password("password123")
    db.session.add(other_user)
    db.session.flush()
    other_tenant = Tenant(user_id=other_user.id, national_id="ID-OTHER")
    db.session.add(other_tenant)
    db.session.commit()

    login(client, "othertenant@test.com")
    resp = client.get(f"/api/v1/leases/{active_lease.id}/statement")
    assert resp.status_code == 403


def test_lease_statement_api_allowed_for_own_tenant(client, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.get(f"/api/v1/leases/{active_lease.id}/statement")
    assert resp.status_code == 200
    assert resp.get_json()["lease_id"] == active_lease.id


def test_maintenance_full_lifecycle(client, db, manager, staff, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.post(
        "/maintenance/add",
        data={"title": "AC not cooling", "description": "Warm air only", "category": "HVAC", "severity": "HIGH"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    req = MaintenanceRequest.query.filter_by(title="AC not cooling").first()
    assert req.status == "SUBMITTED"
    client.get("/logout")

    login(client, manager.email)
    resp = client.post(
        f"/maintenance/{req.id}/update",
        data={"action": "assign", "staff_id": staff.id, "target_date": str(date.today() + timedelta(days=2))},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    db.session.refresh(req)
    assert req.status == "ASSIGNED"
    assert req.assigned_to == staff.id
    client.get("/logout")

    login(client, staff.email)
    resp = client.post(f"/maintenance/{req.id}/update", data={"action": "start", "notes": "On my way"}, follow_redirects=True)
    db.session.refresh(req)
    assert req.status == "IN_PROGRESS"

    resp = client.post(f"/maintenance/{req.id}/update", data={"action": "complete", "notes": "Fixed"}, follow_redirects=True)
    db.session.refresh(req)
    assert req.status == "COMPLETED"
    client.get("/logout")

    login(client, active_lease.tenant.user.email)
    resp = client.post(f"/maintenance/{req.id}/update", data={"action": "close", "rating": "5"}, follow_redirects=True)
    db.session.refresh(req)
    assert req.status == "CLOSED"
    assert req.satisfaction_rating == 5


def test_maintenance_cost_accumulation(client, db, manager, unit, tenant):
    req = MaintenanceRequest(
        unit_id=unit.id, tenant_id=tenant.id, ticket_number=MaintenanceRequest.generate_ticket_number(), title="x", description="x"
    )
    db.session.add(req)
    db.session.commit()

    login(client, manager.email)
    client.post(f"/maintenance/{req.id}/costs/add", data={"category": "LABOUR", "amount": "40"}, follow_redirects=True)
    client.post(f"/maintenance/{req.id}/costs/add", data={"category": "MATERIALS", "amount": "10.5"}, follow_redirects=True)
    db.session.refresh(req)
    assert req.total_cost == 50.5


def test_reports_page_and_json_export(client, owner, property_, unit):
    login(client, owner.email)
    assert client.get("/reports").status_code == 200
    resp = client.get("/api/v1/reports/export")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert "summary" in payload and "properties" in payload
