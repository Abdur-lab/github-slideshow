from datetime import date

from backend.models import ROLE_OWNER, PropertyExpense
from backend.services.reports import portfolio_performance, property_performance

from tests.conftest import login, make_user


def test_add_expense_as_owner(client, db, owner, property_):
    login(client, owner.email)
    resp = client.post(
        f"/properties/{property_.id}/expenses/add",
        data={"category": "INSURANCE", "description": "Annual property insurance", "amount": "1200.00"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    expenses = PropertyExpense.query.filter_by(property_id=property_.id).all()
    assert len(expenses) == 1
    assert expenses[0].category == "INSURANCE"
    assert expenses[0].amount == 1200.0
    assert b"Annual property insurance" in resp.data


def test_add_expense_requires_description(client, owner, property_):
    login(client, owner.email)
    resp = client.post(
        f"/properties/{property_.id}/expenses/add",
        data={"category": "TAX", "description": "  ", "amount": "100"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert PropertyExpense.query.filter_by(property_id=property_.id).count() == 0


def test_add_expense_requires_positive_amount(client, owner, property_):
    login(client, owner.email)
    resp = client.post(
        f"/properties/{property_.id}/expenses/add",
        data={"category": "TAX", "description": "Bad amount", "amount": "-50"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert PropertyExpense.query.filter_by(property_id=property_.id).count() == 0


def test_invalid_category_falls_back_to_other(client, owner, property_):
    login(client, owner.email)
    client.post(
        f"/properties/{property_.id}/expenses/add",
        data={"category": "NOT_A_CATEGORY", "description": "Weird category", "amount": "50"},
        follow_redirects=True,
    )
    expense = PropertyExpense.query.filter_by(property_id=property_.id).first()
    assert expense is not None
    assert expense.category == "OTHER"


def test_add_expense_blocked_for_tenant(client, active_lease):
    login(client, active_lease.tenant.user.email)
    resp = client.post(
        f"/properties/{active_lease.unit.property_id}/expenses/add",
        data={"category": "TAX", "description": "Should not work", "amount": "50"},
    )
    assert resp.status_code == 403


def test_add_expense_blocked_for_staff(client, staff, property_):
    login(client, staff.email)
    resp = client.post(
        f"/properties/{property_.id}/expenses/add",
        data={"category": "TAX", "description": "Should not work", "amount": "50"},
    )
    assert resp.status_code == 403


def test_add_expense_blocked_for_other_owner(client, db, property_):
    other_owner = make_user(db, "other-owner@test.com", ROLE_OWNER, first="Otto", last="Owner")
    login(client, other_owner.email)
    resp = client.post(
        f"/properties/{property_.id}/expenses/add",
        data={"category": "TAX", "description": "Not my property", "amount": "50"},
    )
    assert resp.status_code == 403
    assert PropertyExpense.query.filter_by(property_id=property_.id).count() == 0


def test_property_performance_includes_expenses(db, owner, property_):
    db.session.add(
        PropertyExpense(property_id=property_.id, category="TAX", description="Property tax", amount=400.0, recorded_by=owner.id)
    )
    db.session.add(
        PropertyExpense(
            property_id=property_.id, category="INSURANCE", description="Insurance", amount=100.0, recorded_by=owner.id
        )
    )
    db.session.commit()

    summary = property_performance(property_)
    assert summary["general_expenses"] == 500.0
    assert summary["total_expenses"] == round(500.0 + summary["maintenance_cost"], 2)
    assert summary["net_income_estimate"] == round(summary["rent_collected"] - summary["total_expenses"], 2)


def test_property_performance_respects_date_range(db, owner, property_):
    db.session.add(
        PropertyExpense(
            property_id=property_.id,
            category="TAX",
            description="Old expense",
            amount=300.0,
            incurred_at=date(2020, 1, 1),
            recorded_by=owner.id,
        )
    )
    db.session.add(
        PropertyExpense(
            property_id=property_.id,
            category="TAX",
            description="Recent expense",
            amount=100.0,
            incurred_at=date.today(),
            recorded_by=owner.id,
        )
    )
    db.session.commit()

    summary = property_performance(property_, start=date.today().replace(day=1))
    assert summary["general_expenses"] == 100.0


def test_portfolio_performance_aggregates_expenses(db, owner, property_):
    db.session.add(
        PropertyExpense(property_id=property_.id, category="TAX", description="Tax", amount=250.0, recorded_by=owner.id)
    )
    db.session.commit()

    portfolio = portfolio_performance([property_])
    assert portfolio["general_expenses"] == 250.0
    assert portfolio["total_expenses"] == round(250.0 + portfolio["maintenance_cost"], 2)
    assert portfolio["net_income_estimate"] == round(portfolio["rent_collected"] - portfolio["total_expenses"], 2)


def test_portfolio_performance_empty_includes_new_keys():
    portfolio = portfolio_performance([])
    assert portfolio["general_expenses"] == 0.0
    assert portfolio["total_expenses"] == 0.0
    assert portfolio["net_income_estimate"] == 0.0


def test_detail_page_shows_expenses(client, db, owner, property_):
    db.session.add(
        PropertyExpense(
            property_id=property_.id, category="MANAGEMENT_FEE", description="Monthly management fee", amount=75.0, recorded_by=owner.id
        )
    )
    db.session.commit()

    login(client, owner.email)
    resp = client.get(f"/properties/{property_.id}")
    assert resp.status_code == 200
    assert b"Monthly management fee" in resp.data
    assert b"Operating Expenses" in resp.data
