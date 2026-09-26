"""Demo data matching the credentials documented in Deliverable 3, Appendix C."""
from datetime import date, timedelta

from backend.extensions import db
from backend.models import (
    Lease,
    MaintenanceCost,
    MaintenanceRequest,
    Property,
    RentPayment,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_OWNER,
    ROLE_STAFF,
    ROLE_TENANT,
    Tenant,
    Unit,
    User,
)

DEMO_PASSWORD = "demo123"


def run_seed():
    db.create_all()

    if User.query.filter_by(email="owner@rentalpro.com").first():
        print("Seed data already present, skipping.")
        return

    admin = User(email="admin@rentalpro.com", first_name="Abdur-Rahmaan", last_name="Ali", role=ROLE_ADMIN)
    admin.set_password(DEMO_PASSWORD)
    owner = User(email="owner@rentalpro.com", first_name="Tendai", last_name="Moyo", role=ROLE_OWNER)
    owner.set_password(DEMO_PASSWORD)
    manager = User(email="manager@rentalpro.com", first_name="Rutendo", last_name="Chikore", role=ROLE_MANAGER)
    manager.set_password(DEMO_PASSWORD)
    staff = User(email="staff@rentalpro.com", first_name="Farai", last_name="Ncube", role=ROLE_STAFF)
    staff.set_password(DEMO_PASSWORD)
    tenant_user = User(email="tenant1@email.com", first_name="Chipo", last_name="Mutasa", role=ROLE_TENANT)
    tenant_user.set_password(DEMO_PASSWORD)
    db.session.add_all([admin, owner, manager, staff, tenant_user])
    db.session.flush()

    tenant = Tenant(
        user_id=tenant_user.id,
        national_id="63-2145789 K 42",
        phone="+263 77 214 5789",
        emergency_contact="Tafadzwa Mutasa +263 71 330 4412",
    )
    db.session.add(tenant)
    db.session.flush()

    property1 = Property(
        owner_id=owner.id,
        name="Avondale Heights",
        address="14 King George Road, Avondale",
        city="Harare",
        country="Zimbabwe",
        type="RESIDENTIAL",
        currency="USD",
        description="A mid-size residential block in Avondale, close to Avondale Shopping Centre.",
        property_code=Property.generate_property_code(),
        latitude=-17.7936,
        longitude=31.0380,
    )
    property2 = Property(
        owner_id=owner.id,
        name="Samora Machel Retail Row",
        address="45 Samora Machel Avenue",
        city="Harare",
        country="Zimbabwe",
        type="COMMERCIAL",
        currency="USD",
        property_code=Property.generate_property_code(),
        latitude=-17.8290,
        longitude=31.0490,
    )
    db.session.add_all([property1, property2])
    db.session.flush()

    units = []
    for i in range(1, 5):
        u = Unit(
            property_id=property1.id,
            unit_number=str(100 + i),
            floor=str(1 + i // 3),
            type="1BR" if i % 2 else "2BR",
            size_sqm=55.0 + i * 5,
            monthly_rent=800.0 + i * 50,
            deposit=800.0,
            unit_code=Unit.generate_unit_code(property1.property_code, str(100 + i)),
        )
        units.append(u)
    for i in range(1, 3):
        u = Unit(
            property_id=property2.id,
            unit_number=f"S{i}",
            type="SHOP",
            size_sqm=40.0,
            monthly_rent=1500.0,
            deposit=1500.0,
            unit_code=Unit.generate_unit_code(property2.property_code, f"S{i}"),
        )
        units.append(u)
    db.session.add_all(units)
    db.session.flush()

    lease_unit = units[0]
    lease = Lease(
        unit_id=lease_unit.id,
        tenant_id=tenant.id,
        start_date=date.today() - timedelta(days=200),
        end_date=date.today() + timedelta(days=165),
        monthly_rent=lease_unit.monthly_rent,
        deposit=lease_unit.deposit,
        due_day=1,
    )
    lease_unit.status = "OCCUPIED"
    db.session.add(lease)
    db.session.flush()

    payment = RentPayment(
        lease_id=lease.id,
        amount=lease.monthly_rent,
        method="BANK_TRANSFER",
        receipt_number=RentPayment.generate_receipt_number(),
        recorded_by=manager.id,
        notes="Seed data — first month's rent.",
    )
    db.session.add(payment)

    request1 = MaintenanceRequest(
        unit_id=lease_unit.id,
        tenant_id=tenant.id,
        ticket_number=MaintenanceRequest.generate_ticket_number(),
        title="Leaking kitchen faucet",
        description="The kitchen faucet has been dripping constantly for two days.",
        category="PLUMBING",
        severity="MEDIUM",
        status="ASSIGNED",
        assigned_to=staff.id,
        target_date=date.today() + timedelta(days=3),
    )
    db.session.add(request1)
    db.session.flush()
    db.session.add(MaintenanceCost(request_id=request1.id, category="MATERIALS", amount=25.0, recorded_by=manager.id, description="Replacement washer"))

    db.session.commit()
    print("Seeded: 5 users, 2 properties, 6 units, 1 lease, 1 payment, 1 maintenance request.")
