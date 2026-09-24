from backend.models import LeaseCharge, MeterReading

from tests.conftest import login


def test_first_reading_records_baseline_no_charge(client, db, owner, active_lease):
    active_lease.unit.property.electricity_rate = 0.20
    db.session.commit()

    login(client, owner.email)
    resp = client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-01-01", "reading_value": "100"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    readings = MeterReading.query.filter_by(unit_id=active_lease.unit_id).all()
    assert len(readings) == 1
    assert readings[0].consumption is None
    assert readings[0].charge_id is None
    assert LeaseCharge.query.filter_by(lease_id=active_lease.id, charge_type="ELECTRICITY").count() == 0


def test_second_reading_bills_consumption(client, db, owner, active_lease):
    active_lease.unit.property.electricity_rate = 0.20
    db.session.commit()
    login(client, owner.email)

    client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-01-01", "reading_value": "100"},
    )
    resp = client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-02-01", "reading_value": "150"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    charge = LeaseCharge.query.filter_by(lease_id=active_lease.id, charge_type="ELECTRICITY").first()
    assert charge is not None
    assert charge.amount == 10.0  # 50 units * 0.20

    reading = MeterReading.query.filter_by(unit_id=active_lease.unit_id).order_by(MeterReading.reading_date.desc()).first()
    assert reading.consumption == 50.0
    assert reading.charge_id == charge.id


def test_zero_reading_allowed_for_new_meter(client, db, owner, active_lease):
    login(client, owner.email)
    resp = client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-01-01", "reading_value": "0"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    reading = MeterReading.query.filter_by(unit_id=active_lease.unit_id).first()
    assert reading is not None
    assert reading.reading_value == 0.0


def test_reading_lower_than_previous_rejected(client, db, owner, active_lease):
    login(client, owner.email)
    client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-01-01", "reading_value": "100"},
    )
    resp = client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-02-01", "reading_value": "80"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert MeterReading.query.filter_by(unit_id=active_lease.unit_id).count() == 1


def test_add_meter_reading_blocked_for_tenant(client, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-01-01", "reading_value": "100"},
    )
    assert resp.status_code == 403


def test_add_meter_reading_blocked_for_staff(client, staff, active_lease):
    login(client, staff.email)
    resp = client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-01-01", "reading_value": "100"},
    )
    assert resp.status_code == 403


def test_balance_reflects_electricity_charge(client, db, owner, active_lease):
    active_lease.unit.property.electricity_rate = 0.50
    db.session.commit()
    balance_before = active_lease.balance

    login(client, owner.email)
    client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-01-01", "reading_value": "0"},
    )
    client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-02-01", "reading_value": "20"},
    )

    assert active_lease.balance == round(balance_before + 10.0, 2)


def test_statement_page_shows_meter_readings(client, db, owner, active_lease):
    active_lease.unit.property.electricity_rate = 0.20
    db.session.commit()
    login(client, owner.email)
    client.post(
        f"/rent/{active_lease.id}/meter/add-reading",
        data={"reading_date": "2024-01-01", "reading_value": "100"},
    )
    resp = client.get(f"/rent/{active_lease.id}/statement")
    assert resp.status_code == 200
    assert b"100" in resp.data
