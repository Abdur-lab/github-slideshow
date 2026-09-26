"""Demo data matching the credentials documented in Deliverable 3, Appendix C."""
from datetime import date, datetime, timedelta

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
    property3 = Property(
        owner_id=owner.id,
        name="Julius Nyerere Business Centre",
        address="78 Julius Nyerere Way",
        city="Harare",
        country="Zimbabwe",
        type="MIXED",
        currency="USD",
        description="Offices and ground-floor shops in the Harare CBD.",
        property_code=Property.generate_property_code(),
        latitude=-17.8316,
        longitude=31.0457,
    )
    property4 = Property(
        owner_id=owner.id,
        name="Eastlea Garden Flats",
        address="18 Glenara Avenue South, Eastlea",
        city="Harare",
        country="Zimbabwe",
        type="RESIDENTIAL",
        currency="USD",
        description="Walk-up studio and one-bedroom flats in Eastlea.",
        property_code=Property.generate_property_code(),
        latitude=-17.8235,
        longitude=31.0735,
    )
    property5 = Property(
        owner_id=owner.id,
        name="Vainona Park Townhouses",
        address="12 Vainona Drive, Vainona",
        city="Harare",
        country="Zimbabwe",
        type="RESIDENTIAL",
        currency="USD",
        description="Three-bedroom townhouses in a gated complex in Vainona.",
        property_code=Property.generate_property_code(),
        latitude=-17.7445,
        longitude=31.0835,
    )
    db.session.add_all([property1, property2, property3, property4, property5])
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
    for prop, unit_number, unit_type, size, rent in [
        (property3, "O1", "OFFICE", 60.0, 1200.0),
        (property3, "O2", "OFFICE", 60.0, 1200.0),
        (property3, "S1", "SHOP", 45.0, 1400.0),
        (property4, "1", "STUDIO", 30.0, 450.0),
        (property4, "2", "STUDIO", 30.0, 450.0),
        (property4, "3", "1BR", 45.0, 600.0),
        (property4, "4", "1BR", 45.0, 600.0),
        (property5, "T1", "3BR", 160.0, 1800.0),
        (property5, "T2", "3BR", 160.0, 1800.0),
        (property5, "T3", "3BR", 160.0, 1800.0),
    ]:
        units.append(
            Unit(
                property_id=prop.id,
                unit_number=unit_number,
                type=unit_type,
                size_sqm=size,
                monthly_rent=rent,
                deposit=rent,
                unit_code=Unit.generate_unit_code(prop.property_code, unit_number),
            )
        )
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

    # More Harare tenants across the portfolio. Each pays every month due so
    # far, except those with months_behind > 0, who are that many months in arrears.
    unit_at = {(u.property_id, u.unit_number): u for u in units}
    extra_tenants = [
        # (email, first, last, national_id, phone, emergency contact, property, unit, days since lease start, months behind, payment method)
        ("tenant2@email.com", "Tatenda", "Chiweshe", "63-1874520 F 18", "+263 77 318 4520", "Rudo Chiweshe +263 71 552 0913", property4, "1", 150, 0, "ONLINE"),
        ("tenant3@email.com", "Nyasha", "Mapfumo", "08-2231984 H 25", "+263 78 224 1984", "Farai Mapfumo +263 77 902 1175", property4, "3", 95, 1, "CASH"),
        ("tenant4@email.com", "Kudakwashe", "Sibanda", "29-1150362 P 07", "+263 71 115 0362", "Thandeka Sibanda +263 78 640 2231", property5, "T1", 240, 0, "BANK_TRANSFER"),
        ("tenant5@email.com", "Rumbidzai", "Marufu", "63-2790451 Q 42", "+263 77 279 0451", "Tonderai Marufu +263 71 118 7760", property5, "T2", 60, 0, "BANK_TRANSFER"),
        ("tenant6@email.com", "Simbarashe", "Dube", "58-0942716 D 13", "+263 78 094 2716", "Chiedza Dube +263 77 431 6628", property3, "O1", 300, 0, "BANK_TRANSFER"),
        ("tenant7@email.com", "Precious", "Ndlovu", "08-1627735 L 08", "+263 71 162 7735", "Sipho Ndlovu +263 78 115 9942", property3, "S1", 130, 1, "CHEQUE"),
        ("tenant8@email.com", "Blessing", "Makoni", "63-3318845 W 50", "+263 77 331 8845", "Ruvimbo Makoni +263 71 820 3317", property2, "S1", 210, 0, "BANK_TRANSFER"),
        ("tenant9@email.com", "Munyaradzi", "Zvobgo", "75-2046193 T 22", "+263 78 204 6193", "Vimbai Zvobgo +263 77 665 0184", property1, "102", 45, 0, "ONLINE"),
    ]
    extra_payments = 0
    for email, first, last, national_id, phone, emergency, prop, unit_number, days_in, months_behind, method in extra_tenants:
        user = User(email=email, first_name=first, last_name=last, role=ROLE_TENANT)
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)
        db.session.flush()
        t = Tenant(user_id=user.id, national_id=national_id, phone=phone, emergency_contact=emergency)
        db.session.add(t)
        db.session.flush()

        unit = unit_at[(prop.id, unit_number)]
        start = date.today() - timedelta(days=days_in)
        extra_lease = Lease(
            unit_id=unit.id,
            tenant_id=t.id,
            start_date=start,
            end_date=start + timedelta(days=365),
            monthly_rent=unit.monthly_rent,
            deposit=unit.deposit,
            due_day=1,
        )
        unit.status = "OCCUPIED"
        db.session.add(extra_lease)
        db.session.flush()

        periods_due = round(extra_lease.total_due_to_date() / extra_lease.monthly_rent)
        for i in range(max(0, periods_due - months_behind)):
            db.session.add(
                RentPayment(
                    lease_id=extra_lease.id,
                    amount=extra_lease.monthly_rent,
                    method=method,
                    receipt_number=RentPayment.generate_receipt_number(),
                    paid_at=datetime.combine(extra_lease.first_due_date(), datetime.min.time()) + timedelta(days=30 * i),
                    recorded_by=manager.id,
                )
            )
            extra_payments += 1

    db.session.commit()
    print(
        f"Seeded: {5 + len(extra_tenants)} users, 5 properties, 16 units, {1 + len(extra_tenants)} leases, "
        f"{1 + extra_payments} payments, 1 maintenance request."
    )
