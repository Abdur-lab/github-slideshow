"""FR-015 (tenant history per unit) and FR-036 (maintenance summary per
property per period)."""
import re
from datetime import date, datetime, timedelta

from backend.models import ROLE_OWNER, ROLE_TENANT, Lease, MaintenanceRequest, Property, Tenant
from backend.services.reports import maintenance_summary
from tests.conftest import login, make_user


def _past_tenant(db, unit, name="Peter", national_id="ID-0002"):
    user = make_user(db, f"{name.lower()}@test.com", ROLE_TENANT, first=name, last="Past")
    tenant = Tenant(user_id=user.id, national_id=national_id, phone="555-0002")
    db.session.add(tenant)
    db.session.flush()
    lease = Lease(unit_id=unit.id, tenant_id=tenant.id, start_date=date.today() - timedelta(days=800),
                  end_date=date.today() - timedelta(days=435), monthly_rent=900.0, deposit=900.0, status="TERMINATED")
    db.session.add(lease)
    db.session.commit()
    return tenant


def _request(db, unit, tenant, status, created_days_ago=0):
    req = MaintenanceRequest(unit_id=unit.id, tenant_id=tenant.id, ticket_number=MaintenanceRequest.generate_ticket_number(),
                             title=f"{status} job", description="x", status=status,
                             created_at=datetime.utcnow() - timedelta(days=created_days_ago))
    db.session.add(req)
    db.session.commit()
    return req


# --- FR-015: tenant history per unit ------------------------------------------------

def test_unit_history_lists_past_and_current_tenants_newest_first(client, db, owner, property_, unit, active_lease):
    _past_tenant(db, unit)
    login(client, owner.email)
    html = client.get(f"/properties/{property_.id}/units/{unit.id}/history").get_data(as_text=True)
    assert "Tenant History" in html
    assert "Tara Tenant" in html and "Peter Past" in html
    assert "ID-0001" in html and "ID-0002" in html
    assert "TERMINATED" in html and "ACTIVE" in html
    assert html.index("Tara Tenant") < html.index("Peter Past")


def test_unit_history_with_no_leases(client, owner, property_, unit):
    login(client, owner.email)
    html = client.get(f"/properties/{property_.id}/units/{unit.id}/history").get_data(as_text=True)
    assert "No tenant has occupied this unit yet." in html


def test_property_page_links_to_unit_history(client, owner, property_, unit):
    login(client, owner.email)
    html = client.get(f"/properties/{property_.id}").get_data(as_text=True)
    assert f"/properties/{property_.id}/units/{unit.id}/history" in html


def test_unit_history_blocked_for_another_owner(client, db, property_, unit):
    make_user(db, "other-owner@test.com", ROLE_OWNER)
    login(client, "other-owner@test.com")
    assert client.get(f"/properties/{property_.id}/units/{unit.id}/history").status_code == 403


def test_unit_history_blocked_for_tenants(client, property_, unit, active_lease):
    login(client, active_lease.tenant.user.email)
    assert client.get(f"/properties/{property_.id}/units/{unit.id}/history").status_code == 403


def test_unit_history_rejects_a_unit_from_another_property(client, db, owner, property_, unit):
    other = Property(owner_id=owner.id, name="Other Block", address="2 Side St", city="Testville", country="Testland",
                     property_code=Property.generate_property_code())
    db.session.add(other)
    db.session.commit()
    login(client, owner.email)
    assert client.get(f"/properties/{other.id}/units/{unit.id}/history").status_code == 404


# --- FR-036: maintenance summary per property per period ----------------------------

def test_maintenance_summary_groups_the_six_stages_into_three(db, property_, unit, tenant):
    for status in ("SUBMITTED", "ACKNOWLEDGED", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CLOSED"):
        _request(db, unit, tenant, status)
    today = date.today()
    summary = maintenance_summary([property_], today - timedelta(days=7), today)
    row = summary["properties"][0]
    assert (row["open"], row["in_progress"], row["closed"], row["total"]) == (3, 1, 2, 6)
    assert summary["totals"] == {"open": 3, "in_progress": 1, "closed": 2, "total": 6}


def test_maintenance_summary_counts_only_requests_raised_in_the_period(db, property_, unit, tenant):
    _request(db, unit, tenant, "SUBMITTED", created_days_ago=0)
    _request(db, unit, tenant, "CLOSED", created_days_ago=40)
    today = date.today()
    recent = maintenance_summary([property_], today - timedelta(days=7), today)["properties"][0]
    assert (recent["open"], recent["closed"], recent["total"]) == (1, 0, 1)
    wider = maintenance_summary([property_], today - timedelta(days=60), today)["properties"][0]
    assert (wider["open"], wider["closed"], wider["total"]) == (1, 1, 2)


def test_maintenance_summary_includes_the_end_date(db, property_, unit, tenant):
    _request(db, unit, tenant, "IN_PROGRESS", created_days_ago=0)
    today = date.today()
    assert maintenance_summary([property_], today, today)["properties"][0]["in_progress"] == 1


def test_reports_page_shows_maintenance_summary_for_the_chosen_period(client, db, owner, property_, unit, tenant):
    _request(db, unit, tenant, "ASSIGNED")
    _request(db, unit, tenant, "COMPLETED")
    start = (date.today() - timedelta(days=3)).isoformat()
    end = date.today().isoformat()
    login(client, owner.email)
    html = client.get(f"/reports?start={start}&end={end}").get_data(as_text=True)
    assert "Maintenance Summary" in html
    assert f"Requests raised between {start} and {end}" in html
    compact = re.sub(r">\s+<", "><", html)
    assert "<td>Test Towers</td><td>1</td><td>0</td><td>1</td><td>2</td>" in compact


def test_reports_page_defaults_to_the_current_month(client, owner, property_):
    login(client, owner.email)
    html = client.get("/reports").get_data(as_text=True)
    first = date.today().replace(day=1).isoformat()
    assert f"Requests raised between {first} and {date.today().isoformat()}" in html


def test_reports_page_rejects_bad_dates(client, owner, property_):
    login(client, owner.email)
    html = client.get("/reports?start=27/09/2026&end=2026-09-30").get_data(as_text=True)
    assert "Dates must be in YYYY-MM-DD format" in html
    assert f"Requests raised between {date.today().replace(day=1).isoformat()}" in html


def test_reports_page_rejects_start_after_end(client, owner, property_):
    login(client, owner.email)
    html = client.get("/reports?start=2026-09-30&end=2026-09-01").get_data(as_text=True)
    assert "The start date must be on or before the end date" in html


# --- FR-036 exports: the maintenance summary as Excel and PDF ----------------------

def test_maintenance_summary_excel_export_has_the_period_and_counts(client, db, owner, property_, unit, tenant):
    import io

    import openpyxl

    _request(db, unit, tenant, "ASSIGNED")
    _request(db, unit, tenant, "IN_PROGRESS")
    _request(db, unit, tenant, "CLOSED")
    _request(db, unit, tenant, "SUBMITTED", created_days_ago=90)
    start = (date.today() - timedelta(days=3)).isoformat()
    end = date.today().isoformat()
    login(client, owner.email)
    resp = client.get(f"/reports/maintenance.xlsx?start={start}&end={end}")
    assert resp.status_code == 200
    assert f"maintenance-summary-portfolio-{start}-to-{end}.xlsx" in resp.headers["Content-Disposition"]
    rows = list(openpyxl.load_workbook(io.BytesIO(resp.data))["Maintenance Summary"].iter_rows(values_only=True))
    assert rows[0][:2] == ("From", start) and rows[1][:2] == ("To", end)
    assert rows[3] == ("Property", "Open", "In Progress", "Closed", "Total")
    assert rows[4] == ("Test Towers", 1, 1, 1, 3)


def test_maintenance_summary_excel_export_adds_a_total_row_for_several_properties(client, db, owner, property_, unit, tenant):
    import io

    import openpyxl

    second = Property(owner_id=owner.id, property_code=Property.generate_property_code(), name="Second Court",
                      address="2 Road", city="Testville", country="Testland")
    db.session.add(second)
    db.session.commit()
    _request(db, unit, tenant, "COMPLETED")
    login(client, owner.email)
    rows = list(openpyxl.load_workbook(io.BytesIO(client.get("/reports/maintenance.xlsx").data)).active.iter_rows(values_only=True))
    assert rows[-1] == ("All properties", 0, 0, 1, 1)


def test_maintenance_summary_pdf_export_for_one_property(client, db, owner, property_, unit, tenant):
    _request(db, unit, tenant, "ASSIGNED")
    login(client, owner.email)
    resp = client.get(f"/reports/maintenance.pdf?property_id={property_.id}")
    assert resp.status_code == 200 and resp.data.startswith(b"%PDF")
    assert f"maintenance-summary-{property_.property_code}-" in resp.headers["Content-Disposition"]


def test_maintenance_summary_exports_render_in_arabic(client, owner, property_):
    import io

    import openpyxl

    login(client, owner.email)
    client.get("/lang/ar")
    pdf = client.get("/reports/maintenance.pdf")
    assert pdf.status_code == 200 and b"DejaVuSans" in pdf.data
    wb = openpyxl.load_workbook(io.BytesIO(client.get("/reports/maintenance.xlsx").data))
    assert wb.sheetnames == ["ملخص الصيانة"] and wb.active.sheet_view.rightToLeft


def test_maintenance_summary_exports_are_limited_to_management_and_own_properties(client, db, property_, tenant):
    other = make_user(db, "other-owner@test.com", ROLE_OWNER)
    login(client, other.email)
    for fmt in ("xlsx", "pdf"):
        assert client.get(f"/reports/maintenance.{fmt}?property_id={property_.id}").status_code in (403, 404)
    client.get("/logout")
    login(client, tenant.user.email)
    for fmt in ("xlsx", "pdf"):
        assert client.get(f"/reports/maintenance.{fmt}").status_code in (302, 403)


def test_reports_page_links_the_exports_to_the_chosen_period(client, owner, property_):
    login(client, owner.email)
    html = client.get("/reports?start=2026-09-01&end=2026-09-30").get_data(as_text=True)
    assert "/reports/maintenance.xlsx?start=2026-09-01&amp;end=2026-09-30" in html
    assert "/reports/maintenance.pdf?start=2026-09-01&amp;end=2026-09-30" in html
