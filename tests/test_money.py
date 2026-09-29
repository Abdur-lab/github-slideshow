"""Amounts are shown the same way everywhere: currency code, thousands separators, two decimals."""
import pathlib

from backend.i18n import money
from backend.models import Property
from backend.services.reports import portfolio_performance
from tests.conftest import login

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "templates"


def test_money_format(app):
    with app.test_request_context():
        assert money(1250, "USD") == "USD 1,250.00"
        assert money(-450.5, "USD") == "USD -450.50"
        assert money(1250) == "1,250.00"
        assert money(None, "USD") == ""


def test_money_keeps_its_order_on_arabic_pages(app):
    with app.test_request_context():
        from flask import session

        session["lang"] = "ar"
        assert money(1250, "USD") == "⁦USD 1,250.00⁩"


def test_templates_format_every_amount_with_the_money_filter():
    assert not [p.name for p in TEMPLATES.rglob("*.html") if '"%.2f"|format' in p.read_text(encoding="utf-8")]


def test_amounts_show_their_currency_on_every_money_screen(client, owner, active_lease):
    login(client, owner.email)
    for url in ("/dashboard", "/rent", "/tenants", f"/tenants/{active_lease.tenant_id}",
                f"/rent/{active_lease.id}/statement", "/reports"):
        assert b"USD " in client.get(url).data, url


def test_portfolio_totals_carry_a_currency_only_when_all_properties_share_it(db, owner, property_):
    assert portfolio_performance([property_])["currency"] == "USD"
    other = Property(
        owner_id=owner.id, name="Rand House", address="1 Main Rd", city="Harare", country="Zimbabwe", currency="ZAR",
        property_code="PROP-ZAR1",
    )
    db.session.add(other)
    db.session.commit()
    assert portfolio_performance([property_, other])["currency"] is None
