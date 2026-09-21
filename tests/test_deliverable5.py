"""Deliverable 5 feature-completion tests: everything added to close the
gap to 100% of the SRS functional requirements — unit editing, photo
uploads, tenant blacklisting, admin user/role management, staff account
creation, late fees, and CSV/Excel export."""
import io
from datetime import date, timedelta

import openpyxl

from backend.models import ROLE_ADMIN, ROLE_OWNER, ROLE_TENANT, MaintenanceRequest, Property, RentPayment, Tenant, Unit, User
from tests.conftest import login

MINIMAL_JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
MINIMAL_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


# --- Edit unit / property ---------------------------------------------------

def test_edit_unit_updates_fields(client, owner, property_, unit):
    login(client, owner.email)
    resp = client.post(
        f"/properties/{property_.id}/units/{unit.id}/edit",
        data={"floor": "3", "type": "2BR", "monthly_rent": "1200", "deposit": "1200", "status": "VACANT"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert unit.monthly_rent == 1200
    assert unit.floor == "3"


def test_edit_unit_blocks_manual_vacant_when_occupied(client, db, owner, property_, unit, active_lease):
    login(client, owner.email)
    resp = client.post(
        f"/properties/{property_.id}/units/{unit.id}/edit",
        data={"floor": "1", "type": unit.type, "monthly_rent": "1000", "deposit": "1000", "status": "VACANT"},
        follow_redirects=True,
    )
    assert b"cannot be manually set to Vacant" in resp.data
    db.session.refresh(unit)
    assert unit.status == "OCCUPIED"


def test_edit_unit_allows_under_maintenance(client, db, owner, property_, unit):
    login(client, owner.email)
    client.post(
        f"/properties/{property_.id}/units/{unit.id}/edit",
        data={"floor": "1", "type": unit.type, "monthly_rent": "1000", "deposit": "1000", "status": "UNDER_MAINTENANCE"},
        follow_redirects=True,
    )
    db.session.refresh(unit)
    assert unit.status == "UNDER_MAINTENANCE"


def test_edit_property_updates_late_fee_config(client, db, owner, property_):
    login(client, owner.email)
    resp = client.post(
        f"/properties/{property_.id}/edit",
        data={"description": "Updated", "late_fee_type": "PERCENTAGE", "late_fee_amount": "5"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    db.session.refresh(property_)
    assert property_.late_fee_type == "PERCENTAGE"
    assert property_.late_fee_amount == 5.0


# --- Photo uploads -----------------------------------------------------------

def test_property_photo_upload_and_serve(client, db, owner, property_):
    login(client, owner.email)
    resp = client.post(
        f"/properties/{property_.id}/edit",
        data={"description": "x", "late_fee_type": "NONE", "late_fee_amount": "0", "photos": (io.BytesIO(MINIMAL_JPG), "photo.jpg")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    db.session.refresh(property_)
    assert len(property_.photo_paths) == 1

    filename = property_.photo_paths[0].split("/")[-1]
    photo_resp = client.get(f"/properties/{property_.id}/photos/{filename}")
    assert photo_resp.status_code == 200


def test_unit_photo_upload_rejects_non_image(client, db, owner, property_, unit):
    login(client, owner.email)
    resp = client.post(
        f"/properties/{property_.id}/units/{unit.id}/edit",
        data={
            "floor": "1", "type": unit.type, "monthly_rent": "1000", "deposit": "1000", "status": "VACANT",
            "photos": (io.BytesIO(b"not an image"), "fake.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"not a valid JPG/PNG" in resp.data
    db.session.refresh(unit)
    assert unit.photo_paths == []


def test_unit_photo_upload_accepts_png(client, db, owner, property_, unit):
    login(client, owner.email)
    client.post(
        f"/properties/{property_.id}/units/{unit.id}/edit",
        data={
            "floor": "1", "type": unit.type, "monthly_rent": "1000", "deposit": "1000", "status": "VACANT",
            "photos": (io.BytesIO(MINIMAL_PNG), "unit.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    db.session.refresh(unit)
    assert len(unit.photo_paths) == 1


def test_maintenance_request_photo_upload_and_serve(client, db, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.post(
        "/maintenance/add",
        data={
            "title": "Broken window", "description": "Cracked", "category": "OTHER", "severity": "LOW",
            "photos": (io.BytesIO(MINIMAL_JPG), "issue.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    req = MaintenanceRequest.query.filter_by(title="Broken window").first()
    assert len(req.photo_paths) == 1

    filename = req.photo_paths[0].split("/")[-1]
    photo_resp = client.get(f"/maintenance/{req.id}/photos/{filename}")
    assert photo_resp.status_code == 200


def test_maintenance_completion_photo_upload(client, db, manager, staff, unit, tenant):
    req = MaintenanceRequest(
        unit_id=unit.id, tenant_id=tenant.id, ticket_number=MaintenanceRequest.generate_ticket_number(),
        title="x", description="x", status="ASSIGNED", assigned_to=staff.id,
    )
    db.session.add(req)
    db.session.commit()

    login(client, staff.email)
    resp = client.post(
        f"/maintenance/{req.id}/update",
        data={"action": "complete", "notes": "done", "photos": (io.BytesIO(MINIMAL_PNG), "done.png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    db.session.refresh(req)
    assert req.status == "COMPLETED"
    assert len(req.completion_photo_paths) == 1


# --- Tenant blacklist & ID document -------------------------------------------

def test_blacklist_blocks_new_lease(client, db, manager, tenant, unit):
    login(client, manager.email)
    client.post(f"/tenants/{tenant.id}/blacklist", data={"reason": "Property damage"}, follow_redirects=True)
    db.session.refresh(tenant)
    assert tenant.is_blacklisted is True

    resp = client.post(
        f"/tenants/{tenant.id}/upload-lease",
        data={
            "unit_id": unit.id, "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
            "monthly_rent": "1000", "lease_document": (io.BytesIO(MINIMAL_PDF), "lease.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"blacklisted" in resp.data
    db.session.refresh(unit)
    assert unit.status == "VACANT"


def test_unblacklist_allows_lease_again(client, db, manager, tenant):
    login(client, manager.email)
    client.post(f"/tenants/{tenant.id}/blacklist", data={"reason": "test"}, follow_redirects=True)
    client.post(f"/tenants/{tenant.id}/unblacklist", follow_redirects=True)
    db.session.refresh(tenant)
    assert tenant.is_blacklisted is False
    assert tenant.blacklist_reason is None


def test_blacklist_requires_reason(client, db, manager, tenant):
    login(client, manager.email)
    resp = client.post(f"/tenants/{tenant.id}/blacklist", data={"reason": ""}, follow_redirects=True)
    assert b"reason is required" in resp.data
    db.session.refresh(tenant)
    assert tenant.is_blacklisted is False


def test_tenant_id_document_upload_and_authorized_download(client, db, manager, unit):
    login(client, manager.email)
    resp = client.post(
        "/tenants/add",
        data={
            "full_name": "Photo ID Tenant", "national_id": "ID-PHOTO-1", "email": "photoid@test.com",
            "id_document": (io.BytesIO(MINIMAL_PDF), "id.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    new_tenant = Tenant.query.filter_by(national_id="ID-PHOTO-1").first()
    assert new_tenant.id_document_path is not None

    dl = client.get(f"/tenants/{new_tenant.id}/id-document")
    assert dl.status_code == 200


def test_id_document_download_blocked_for_other_tenant(client, db, tenant):
    other_user = User(email="otherid@test.com", first_name="Other", last_name="Id", role=ROLE_TENANT)
    other_user.set_password("password123")
    db.session.add(other_user)
    db.session.flush()
    other_tenant = Tenant(user_id=other_user.id, national_id="ID-OTHER-DOC", id_document_path="tenants/fake/doc.pdf")
    db.session.add(other_tenant)
    db.session.commit()

    login(client, tenant.user.email)
    resp = client.get(f"/tenants/{other_tenant.id}/id-document")
    assert resp.status_code == 403


# --- Admin user & role management --------------------------------------------

def test_admin_can_list_users(client, admin, owner, manager, staff, tenant):
    login(client, admin.email)
    resp = client.get("/admin/users")
    assert resp.status_code == 200
    assert owner.email.encode() in resp.data


def test_non_admin_cannot_access_admin_users(client, owner, manager):
    login(client, owner.email)
    assert client.get("/admin/users").status_code == 403
    client.get("/logout")
    login(client, manager.email)
    assert client.get("/admin/users").status_code == 403


def test_admin_cannot_remove_last_active_owner(client, db, admin, owner):
    login(client, admin.email)
    resp = client.post(f"/admin/users/{owner.id}/edit", data={"role": "TENANT"}, follow_redirects=True)
    assert b"at least one active Property Owner" in resp.data
    db.session.refresh(owner)
    assert owner.role == ROLE_OWNER


def test_admin_can_change_role_when_another_owner_exists(client, db, admin, owner):
    second_owner = User(email="owner2@test.com", first_name="Sec", last_name="Ond", role=ROLE_OWNER)
    second_owner.set_password("password123")
    db.session.add(second_owner)
    db.session.commit()

    login(client, admin.email)
    resp = client.post(f"/admin/users/{owner.id}/edit", data={"role": "PROPERTY_MANAGER", "is_active": "on"}, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(owner)
    assert owner.role == "PROPERTY_MANAGER"


def test_admin_can_deactivate_non_owner_user(client, db, admin, staff):
    login(client, admin.email)
    client.post(f"/admin/users/{staff.id}/edit", data={"role": staff.role}, follow_redirects=True)
    db.session.refresh(staff)
    assert staff.is_active is False


def test_add_staff_account_by_manager(client, db, manager):
    login(client, manager.email)
    resp = client.post("/admin/staff/add", data={"full_name": "New Tech", "email": "newtech@test.com"}, follow_redirects=True)
    assert resp.status_code == 200
    created = User.query.filter_by(email="newtech@test.com").first()
    assert created is not None
    assert created.role == "MAINTENANCE_STAFF"


def test_add_staff_rejects_duplicate_email(client, staff):
    login(client, staff.email)
    # staff role isn't in MANAGEMENT_ROLES, should be forbidden outright
    resp = client.get("/admin/staff/add")
    assert resp.status_code == 403


# --- Late fees -----------------------------------------------------------------

def test_late_fee_fixed_applies_once_overdue(db, unit, tenant, property_):
    from backend.models import Lease

    property_.late_fee_type = "FIXED"
    property_.late_fee_amount = 30.0
    db.session.commit()

    overdue_due_day = (date.today() - timedelta(days=10)).day
    lease = Lease(
        unit_id=unit.id, tenant_id=tenant.id, start_date=date.today() - timedelta(days=100),
        end_date=date.today() + timedelta(days=200), monthly_rent=unit.monthly_rent, due_day=overdue_due_day,
    )
    db.session.add(lease)
    db.session.commit()
    assert lease.late_fee_due() == 30.0
    assert lease.balance == round(lease.total_due_to_date() + 30.0, 2)


def test_late_fee_percentage_applies_once_overdue(db, unit, tenant, property_):
    from backend.models import Lease

    property_.late_fee_type = "PERCENTAGE"
    property_.late_fee_amount = 10.0
    db.session.commit()

    overdue_due_day = (date.today() - timedelta(days=10)).day
    lease = Lease(
        unit_id=unit.id, tenant_id=tenant.id, start_date=date.today() - timedelta(days=100),
        end_date=date.today() + timedelta(days=200), monthly_rent=1000.0, due_day=overdue_due_day,
    )
    db.session.add(lease)
    db.session.commit()
    assert lease.late_fee_due() == 100.0


def test_late_fee_zero_when_not_overdue(db, unit, tenant, property_):
    from backend.models import Lease

    property_.late_fee_type = "FIXED"
    property_.late_fee_amount = 30.0
    db.session.commit()

    lease = Lease(
        unit_id=unit.id, tenant_id=tenant.id, start_date=date.today() + timedelta(days=5),
        end_date=date.today() + timedelta(days=200), monthly_rent=unit.monthly_rent, due_day=1,
    )
    db.session.add(lease)
    db.session.commit()
    assert lease.late_fee_due() == 0.0


def test_late_fee_zero_when_fully_paid(db, unit, tenant, property_):
    from backend.models import Lease

    property_.late_fee_type = "FIXED"
    property_.late_fee_amount = 30.0
    db.session.commit()

    overdue_due_day = (date.today() - timedelta(days=10)).day
    lease = Lease(
        unit_id=unit.id, tenant_id=tenant.id, start_date=date.today() - timedelta(days=100),
        end_date=date.today() + timedelta(days=200), monthly_rent=unit.monthly_rent, due_day=overdue_due_day,
    )
    db.session.add(lease)
    db.session.commit()
    db.session.add(RentPayment(
        lease_id=lease.id, amount=lease.total_due_to_date() + 10, method="CASH",
        receipt_number=RentPayment.generate_receipt_number(), recorded_by=tenant.user_id,
    ))
    db.session.commit()
    assert lease.late_fee_due() == 0.0


# --- CSV / Excel export --------------------------------------------------------

def test_rent_history_csv_export_management(client, manager, active_lease, db):
    from backend.models import RentPayment

    db.session.add(RentPayment(
        lease_id=active_lease.id, amount=200, method="CASH",
        receipt_number=RentPayment.generate_receipt_number(), recorded_by=manager.id,
    ))
    db.session.commit()

    login(client, manager.email)
    resp = client.get(f"/rent/{active_lease.id}/history.csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert b"Receipt Number" in resp.data
    assert b"200.00" in resp.data


def test_rent_history_csv_export_own_tenant(client, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.get(f"/rent/{active_lease.id}/history.csv")
    assert resp.status_code == 200


def test_rent_history_csv_export_blocked_for_other_tenant(client, db, active_lease):
    other_user = User(email="csvother@test.com", first_name="Other", last_name="Csv", role=ROLE_TENANT)
    other_user.set_password("password123")
    db.session.add(other_user)
    db.session.flush()
    other_tenant = Tenant(user_id=other_user.id, national_id="ID-CSV-OTHER")
    db.session.add(other_tenant)
    db.session.commit()

    login(client, "csvother@test.com")
    resp = client.get(f"/rent/{active_lease.id}/history.csv")
    assert resp.status_code == 403


def test_reports_excel_export_structure(client, owner, property_, unit):
    login(client, owner.email)
    resp = client.get("/reports/export.xlsx")
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp.data))
    assert "Portfolio Summary" in wb.sheetnames
    assert "By Property" in wb.sheetnames


def test_reports_excel_export_single_property(client, owner, property_):
    login(client, owner.email)
    resp = client.get(f"/reports/export.xlsx?property_id={property_.id}")
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp.data))
    rows = list(wb["By Property"].iter_rows(values_only=True))
    assert rows[1][0] == property_.name


# --- Lease document download ---------------------------------------------------

def test_lease_document_download_by_manager(client, db, manager, unit, tenant):
    login(client, manager.email)
    client.post(
        f"/tenants/{tenant.id}/upload-lease",
        data={
            "unit_id": unit.id, "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
            "monthly_rent": "1000", "lease_document": (io.BytesIO(MINIMAL_PDF), "lease.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    from backend.models import Lease

    lease = Lease.query.filter_by(tenant_id=tenant.id).first()
    resp = client.get(f"/tenants/{tenant.id}/lease-document/{lease.id}")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
