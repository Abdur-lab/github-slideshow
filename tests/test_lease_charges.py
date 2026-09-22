from backend.models import LeaseCharge

from tests.conftest import login


def test_total_charges_zero_when_none(active_lease):
    assert active_lease.total_charges == 0.0


def test_charge_folds_into_balance(db, active_lease):
    balance_before = active_lease.balance
    charge = LeaseCharge(
        lease_id=active_lease.id,
        charge_type="SUNDRY",
        description="Locksmith call-out",
        amount=45.0,
        recorded_by=active_lease.tenant.user_id,
    )
    db.session.add(charge)
    db.session.commit()

    assert active_lease.total_charges == 45.0
    assert active_lease.balance == round(balance_before + 45.0, 2)


def test_add_charge_as_owner(client, owner, active_lease):
    login(client, owner.email)
    resp = client.post(
        f"/rent/{active_lease.id}/charges/add",
        data={"charge_type": "OPERATIONAL", "description": "Common area cleaning", "amount": "75.50"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    charges = LeaseCharge.query.filter_by(lease_id=active_lease.id).all()
    assert len(charges) == 1
    assert charges[0].charge_type == "OPERATIONAL"
    assert charges[0].amount == 75.50
    assert b"Common area cleaning" in resp.data


def test_add_charge_requires_positive_amount(client, owner, active_lease):
    login(client, owner.email)
    resp = client.post(
        f"/rent/{active_lease.id}/charges/add",
        data={"charge_type": "SUNDRY", "description": "Bad amount", "amount": "-5"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert LeaseCharge.query.filter_by(lease_id=active_lease.id).count() == 0


def test_add_charge_requires_description(client, owner, active_lease):
    login(client, owner.email)
    resp = client.post(
        f"/rent/{active_lease.id}/charges/add",
        data={"charge_type": "SUNDRY", "description": "  ", "amount": "10"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert LeaseCharge.query.filter_by(lease_id=active_lease.id).count() == 0


def test_add_charge_blocked_for_tenant(client, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.post(
        f"/rent/{active_lease.id}/charges/add",
        data={"charge_type": "SUNDRY", "description": "Should not work", "amount": "10"},
    )
    assert resp.status_code == 403
    assert LeaseCharge.query.filter_by(lease_id=active_lease.id).count() == 0


def test_add_charge_blocked_for_staff(client, staff, active_lease):
    login(client, staff.email)
    resp = client.post(
        f"/rent/{active_lease.id}/charges/add",
        data={"charge_type": "SUNDRY", "description": "Should not work", "amount": "10"},
    )
    assert resp.status_code == 403


def test_invalid_charge_type_falls_back_to_operational(client, owner, active_lease):
    login(client, owner.email)
    client.post(
        f"/rent/{active_lease.id}/charges/add",
        data={"charge_type": "NOT_A_TYPE", "description": "Weird type", "amount": "10"},
        follow_redirects=True,
    )
    charge = LeaseCharge.query.filter_by(lease_id=active_lease.id).first()
    assert charge is not None
    assert charge.charge_type == "OPERATIONAL"


def test_statement_page_shows_charges(client, db, owner, active_lease):
    charge = LeaseCharge(
        lease_id=active_lease.id,
        charge_type="OPERATIONAL",
        description="Elevator maintenance",
        amount=120.0,
        recorded_by=owner.id,
    )
    db.session.add(charge)
    db.session.commit()

    login(client, owner.email)
    resp = client.get(f"/rent/{active_lease.id}/statement")
    assert resp.status_code == 200
    assert b"Elevator maintenance" in resp.data
    assert b"120.00" in resp.data


def test_statement_pdf_includes_charges(client, db, owner, active_lease):
    charge = LeaseCharge(
        lease_id=active_lease.id,
        charge_type="SUNDRY",
        description="Gate remote replacement",
        amount=30.0,
        recorded_by=owner.id,
    )
    db.session.add(charge)
    db.session.commit()

    login(client, owner.email)
    resp = client.get(f"/rent/{active_lease.id}/statement.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
