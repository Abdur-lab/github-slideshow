from backend.models import Property
from tests.conftest import login


def test_add_property_with_location(client, db, owner):
    login(client, owner.email)
    resp = client.post(
        "/properties/add",
        data={
            "name": "Marina Heights",
            "address": "1 Marina Walk",
            "city": "Testville",
            "country": "Testland",
            "type": "RESIDENTIAL",
            "currency": "USD",
            "latitude": "25.0805",
            "longitude": "55.1403",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    prop = Property.query.filter_by(name="Marina Heights").first()
    assert prop is not None
    assert prop.latitude == 25.0805
    assert prop.longitude == 55.1403
    assert prop.has_location is True


def test_add_property_without_location_leaves_coordinates_null(client, db, owner):
    login(client, owner.email)
    client.post(
        "/properties/add",
        data={"name": "No Pin Villas", "address": "2 Quiet Rd", "city": "Testville", "country": "Testland", "type": "RESIDENTIAL", "currency": "USD"},
        follow_redirects=True,
    )
    prop = Property.query.filter_by(name="No Pin Villas").first()
    assert prop.latitude is None
    assert prop.longitude is None
    assert prop.has_location is False


def test_add_property_rejects_one_sided_coordinates(client, db, owner):
    login(client, owner.email)
    resp = client.post(
        "/properties/add",
        data={
            "name": "Half Pin Estates",
            "address": "3 Odd Ave",
            "city": "Testville",
            "country": "Testland",
            "type": "RESIDENTIAL",
            "currency": "USD",
            "latitude": "25.0805",
        },
        follow_redirects=True,
    )
    assert b"Set both latitude and longitude" in resp.data
    assert Property.query.filter_by(name="Half Pin Estates").first() is None


def test_add_property_rejects_out_of_range_coordinates(client, db, owner):
    login(client, owner.email)
    resp = client.post(
        "/properties/add",
        data={
            "name": "Bad Pin Towers",
            "address": "4 Odd Ave",
            "city": "Testville",
            "country": "Testland",
            "type": "RESIDENTIAL",
            "currency": "USD",
            "latitude": "500",
            "longitude": "55.14",
        },
        follow_redirects=True,
    )
    assert b"Map location is invalid" in resp.data
    assert Property.query.filter_by(name="Bad Pin Towers").first() is None


def test_edit_property_sets_and_clears_location(client, db, owner, property_):
    login(client, owner.email)
    resp = client.post(
        f"/properties/{property_.id}/edit",
        data={"description": "", "late_fee_type": "NONE", "late_fee_amount": "0", "electricity_rate": "0", "latitude": "25.2", "longitude": "55.3"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    db.session.refresh(property_)
    assert property_.latitude == 25.2
    assert property_.longitude == 55.3

    client.post(
        f"/properties/{property_.id}/edit",
        data={"description": "", "late_fee_type": "NONE", "late_fee_amount": "0", "electricity_rate": "0", "latitude": "", "longitude": ""},
        follow_redirects=True,
    )
    db.session.refresh(property_)
    assert property_.latitude is None
    assert property_.longitude is None


def test_property_detail_shows_map_only_when_located(client, db, owner, property_):
    login(client, owner.email)
    resp = client.get(f"/properties/{property_.id}")
    assert b"data-map-static" not in resp.data

    property_.latitude = 25.2
    property_.longitude = 55.3
    db.session.commit()
    resp = client.get(f"/properties/{property_.id}")
    assert b"data-map-static" in resp.data


def test_properties_map_view_lists_only_located_properties(client, db, owner, property_):
    login(client, owner.email)
    resp = client.get("/properties/map")
    assert resp.status_code == 200
    assert b"No properties have a map location set yet" in resp.data

    property_.latitude = 25.2
    property_.longitude = 55.3
    db.session.commit()
    resp = client.get("/properties/map")
    assert b"portfolio-map-data" in resp.data
    assert property_.name.encode() in resp.data


def test_properties_map_view_requires_login(client):
    resp = client.get("/properties/map", follow_redirects=True)
    assert b"RentalPro" in resp.data and b"Properties Map" not in resp.data
