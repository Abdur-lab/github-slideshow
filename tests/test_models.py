import re
from datetime import date, timedelta

import pytest

from backend.models import (
    Lease,
    MaintenanceCost,
    MaintenanceRequest,
    PasswordReset,
    Property,
    RentPayment,
    TenantInvitation,
    Unit,
)


def test_password_hash_and_check(db, owner):
    assert owner.password_hash != "password123"
    assert owner.check_password("password123")
    assert not owner.check_password("wrong-password")


def test_full_name_property(owner):
    assert owner.full_name == "Olivia Owner"


def test_property_occupancy_rate_no_zero_division(property_):
    assert property_.occupancy_rate == 0.0


def test_property_occupancy_rate_with_units(db, property_, unit):
    unit2 = Unit(
        property_id=property_.id,
        unit_number="102",
        monthly_rent=1000.0,
        unit_code=Unit.generate_unit_code(property_.property_code, "102"),
        status="OCCUPIED",
    )
    db.session.add(unit2)
    db.session.commit()
    assert property_.occupancy_rate == 50.0


def test_property_code_format():
    code = Property.generate_property_code()
    assert re.match(r"^PROP-[0-9A-F]{4}$", code)


def test_lease_balance_never_negative_when_overpaid(db, active_lease):
    payment = RentPayment(
        lease_id=active_lease.id,
        amount=active_lease.monthly_rent * 10,
        method="CASH",
        receipt_number=RentPayment.generate_receipt_number(),
        recorded_by=active_lease.tenant.user_id,
    )
    db.session.add(payment)
    db.session.commit()
    assert active_lease.balance == 0.0
    assert active_lease.credit > 0


def test_lease_total_paid_accumulates(db, active_lease):
    for _ in range(3):
        db.session.add(
            RentPayment(
                lease_id=active_lease.id,
                amount=100.0,
                method="CASH",
                receipt_number=RentPayment.generate_receipt_number(),
                recorded_by=active_lease.tenant.user_id,
            )
        )
    db.session.commit()
    assert active_lease.total_paid == 300.0


def test_first_due_date_mid_month_start(db, unit, tenant):
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=date(2025, 1, 15),
        end_date=date(2025, 12, 31),
        monthly_rent=1000,
        due_day=1,
    )
    # start is after due_day=1 in January, so first due date rolls to February 1
    assert lease.first_due_date() == date(2025, 2, 1)


def test_first_due_date_day29_non_leap_year(db, unit, tenant):
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        monthly_rent=1000,
        due_day=31,
    )
    # 2025 is not a leap year; February has 28 days, so due_day clips to 28
    assert lease._clip_day(2025, 2) == 28


def test_total_due_to_date_before_first_due(db, unit, tenant):
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=date.today() + timedelta(days=10),
        end_date=date.today() + timedelta(days=400),
        monthly_rent=1000,
        due_day=1,
    )
    assert lease.total_due_to_date(as_of=date.today()) == 0.0


def test_receipt_number_format():
    receipt = RentPayment.generate_receipt_number()
    assert re.match(r"^RCP-\d{8}-[0-9A-F]{6}$", receipt)


def test_receipt_numbers_unique_under_rapid_creation():
    receipts = {RentPayment.generate_receipt_number() for _ in range(25)}
    assert len(receipts) == 25


def test_ticket_number_format():
    ticket = MaintenanceRequest.generate_ticket_number()
    assert re.match(r"^MNT-\d{8}-[0-9A-F]{4}$", ticket)


def test_maintenance_cost_aggregation(db, unit, tenant, manager):
    req = MaintenanceRequest(
        unit_id=unit.id,
        tenant_id=tenant.id,
        ticket_number=MaintenanceRequest.generate_ticket_number(),
        title="Broken window",
        description="Cracked glass",
    )
    db.session.add(req)
    db.session.flush()
    db.session.add_all(
        [
            MaintenanceCost(request_id=req.id, amount=50.0, recorded_by=manager.id),
            MaintenanceCost(request_id=req.id, amount=75.5, recorded_by=manager.id),
        ]
    )
    db.session.commit()
    assert req.total_cost == 125.5


def test_maintenance_request_overdue_detection(db, unit, tenant):
    req = MaintenanceRequest(
        unit_id=unit.id,
        tenant_id=tenant.id,
        ticket_number=MaintenanceRequest.generate_ticket_number(),
        title="Overdue job",
        description="x",
        status="ASSIGNED",
        target_date=date.today() - timedelta(days=2),
    )
    db.session.add(req)
    db.session.commit()
    assert req.is_overdue

    req.status = "COMPLETED"
    db.session.commit()
    assert not req.is_overdue


def test_tenant_invitation_validity(db, unit):
    valid = TenantInvitation(unit_id=unit.id, email="a@example.com", name="A", expires_at=TenantInvitation.new_token_expiry())
    expired = TenantInvitation(
        unit_id=unit.id, email="b@example.com", name="B", expires_at=TenantInvitation.new_token_expiry(hours=-1)
    )
    db.session.add_all([valid, expired])
    db.session.commit()
    assert valid.is_valid
    assert not expired.is_valid

    valid.accepted = True
    db.session.commit()
    assert not valid.is_valid


def test_password_reset_validity(db, owner):
    valid = PasswordReset(user_id=owner.id, expires_at=PasswordReset.new_token_expiry())
    used = PasswordReset(user_id=owner.id, expires_at=PasswordReset.new_token_expiry(), used=True)
    db.session.add_all([valid, used])
    db.session.commit()
    assert valid.is_valid
    assert not used.is_valid


def test_unit_active_lease(db, unit, active_lease):
    assert unit.active_lease.id == active_lease.id
