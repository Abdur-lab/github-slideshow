import pytest

from backend.i18n import ARABIC, SHONA, TRANSLATIONS
from backend.security import safe_next_url
from tests.conftest import login


def test_english_is_the_default(client):
    resp = client.get("/login")
    assert b'<html lang="en" dir="ltr">' in resp.data
    assert b"Forgot your password?" in resp.data


def test_switching_to_shona_translates_the_login_page(client):
    resp = client.get("/lang/sn?next=/login", follow_redirects=True)
    assert b'<html lang="sn" dir="ltr">' in resp.data
    assert "Wakanganwa pasiwedhi yako?".encode() in resp.data
    assert b"Forgot your password?" not in resp.data


def test_language_choice_survives_login_and_translates_the_nav(client, owner):
    client.get("/lang/sn")
    resp = login(client, "owner@test.com")
    assert "Dhashibhodhi yeZvivakwa".encode() in resp.data
    assert "Zvivakwa</a>".encode() in resp.data
    assert b">Buda</a>" in resp.data


def test_switching_back_to_english(client, owner):
    client.get("/lang/sn")
    login(client, "owner@test.com")
    resp = client.get("/lang/en?next=/dashboard", follow_redirects=True)
    assert b"Portfolio Dashboard" in resp.data


def test_tenant_portal_in_shona(client, db, active_lease):
    client.get("/lang/sn")
    login(client, active_lease.tenant.user.email)
    resp = client.get("/portal")
    full_name = active_lease.tenant.user.full_name
    assert f"Mauya, {full_name}".encode() in resp.data
    assert "Test Towers · Yuniti 101".encode() in resp.data
    assert "Bhadhara Rendi".encode() in resp.data


def test_unknown_language_code_is_ignored(client):
    resp = client.get("/lang/xx?next=/login", follow_redirects=True)
    assert b'<html lang="en" dir="ltr">' in resp.data


def test_language_switch_does_not_open_redirect(client):
    resp = client.get("/lang/sn?next=https://evil.example.com/")
    assert resp.status_code == 302
    assert "evil.example.com" not in resp.headers["Location"]


def test_every_translation_keeps_its_placeholders():
    import re

    for table in TRANSLATIONS.values():
        for english, translated in table.items():
            assert set(re.findall(r"{(\w+)}", english)) == set(re.findall(r"{(\w+)}", translated)), english


def test_arabic_covers_every_shona_phrase():
    assert set(SHONA) <= set(ARABIC)


def _interface_phrases():
    """Every English phrase the interface can show: _() calls in templates and
    routes, plus the stored codes shown through the label filter and badges."""
    import ast
    import pathlib
    import re

    from backend import models
    from backend.i18n import LABEL_ENGLISH

    call = re.compile(r"""\b(?:_|translate)\(\s*('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")""")
    root = pathlib.Path(__file__).resolve().parent.parent
    sources = list((root / "frontend" / "templates").rglob("*.html")) + list((root / "backend").rglob("*.py"))
    phrases = {}
    for path in sources:
        if path.name == "i18n.py":
            continue
        for match in call.finditer(path.read_text(encoding="utf-8")):
            phrases.setdefault(ast.literal_eval(match.group(1)), path.name)
    for name in ("ROLES", "PROPERTY_TYPES", "LATE_FEE_TYPES", "UNIT_TYPES", "PAYMENT_METHODS",
                 "CHARGE_TYPES", "EXPENSE_CATEGORIES", "MAINT_CATEGORIES", "MAINT_SEVERITIES"):
        for code in getattr(models, name):
            phrases.setdefault(LABEL_ENGLISH.get(code, code.replace("_", " ").title()), name)
    for name in ("UNIT_STATUSES", "LEASE_STATUSES", "MAINT_STATUSES", "PROPERTY_STATUSES"):
        for code in getattr(models, name):
            phrases.setdefault(code.replace("_", " "), name)
    return phrases


def test_every_interface_phrase_has_arabic():
    phrases = _interface_phrases()
    assert len(phrases) > 400
    missing = {phrase: source for phrase, source in phrases.items() if phrase not in ARABIC}
    assert not missing


def test_messages_after_an_action_are_shown_in_arabic(client, owner):
    client.get("/lang/ar")
    resp = client.post("/login", data={"email": owner.email, "password": "wrong"}, follow_redirects=True)
    assert "البريد الإلكتروني أو كلمة المرور غير صحيحة.".encode() in resp.data
    assert b"Invalid email or password." not in resp.data


def test_message_values_are_filled_into_the_arabic_sentence(client, owner, property_):
    login(client, owner.email)
    client.get("/lang/ar")
    resp = client.post(
        f"/properties/{property_.id}/add-unit",
        data={"unit_number": "205", "type": "2BR", "monthly_rent": "700", "deposit": "700"},
        follow_redirects=True,
    )
    assert "تمت إضافة الوحدة".encode() in resp.data
    assert b"added." not in resp.data


def test_stored_codes_are_shown_as_words_in_each_language(client, owner, property_):
    login(client, owner.email)
    assert b"Bank Transfer" in client.get("/rent/record").data
    client.get("/lang/ar")
    page = client.get("/rent/record").get_data(as_text=True)
    assert "تحويل بنكي" in page
    assert "BANK_TRANSFER" in page  # the submitted value stays the stored code
    assert "Bank Transfer" not in page


def test_switching_to_arabic_translates_and_turns_the_page_right_to_left(client):
    resp = client.get("/lang/ar?next=/login", follow_redirects=True)
    assert b'<html lang="ar" dir="rtl">' in resp.data
    assert "هل نسيت كلمة المرور؟".encode() in resp.data
    assert b"Forgot your password?" not in resp.data


def test_english_and_shona_stay_left_to_right(client):
    assert b'dir="ltr"' in client.get("/login").data
    assert b'dir="ltr"' in client.get("/lang/sn?next=/login", follow_redirects=True).data


def test_tenant_portal_in_arabic(client, db, active_lease):
    client.get("/lang/ar")
    login(client, active_lease.tenant.user.email)
    html = client.get("/portal").get_data(as_text=True)
    assert f"مرحبًا، {active_lease.tenant.user.full_name}" in html
    assert "Test Towers · الوحدة 101" in html
    assert "ادفع الإيجار الآن" in html


def test_location_names_are_never_translated(client, db, owner, tenant):
    """Property names, street addresses, suburbs, cities and countries are data, not
    interface text, so they must read exactly the same in Shona as in English."""
    from datetime import date, timedelta

    from backend.models import Lease, Property, Unit

    prop = Property(
        owner_id=owner.id,
        name="Eastlea Garden Flats",
        address="45 Samora Machel Avenue, Eastlea",
        city="Harare",
        country="Zimbabwe",
        property_code=Property.generate_property_code(),
        latitude=-17.8235,
        longitude=31.0735,
    )
    db.session.add(prop)
    db.session.flush()
    unit = Unit(property_id=prop.id, unit_number="3", monthly_rent=600.0, deposit=600.0,
                unit_code=Unit.generate_unit_code(prop.property_code, "3"), status="OCCUPIED")
    db.session.add(unit)
    db.session.flush()
    db.session.add(Lease(unit_id=unit.id, tenant_id=tenant.id, start_date=date.today() - timedelta(days=10),
                         end_date=date.today() + timedelta(days=355), monthly_rent=600.0, deposit=600.0))
    db.session.commit()

    location_text = ["Eastlea Garden Flats", "45 Samora Machel Avenue, Eastlea", "Harare", "Zimbabwe"]

    client.get("/lang/sn")
    login(client, "owner@test.com")
    for path in ("/dashboard", "/properties", "/properties/map", "/reports"):
        html = client.get(path).get_data(as_text=True)
        assert "Eastlea Garden Flats" in html, path
    properties_page = client.get("/properties").get_data(as_text=True)
    for text in location_text:
        assert text in properties_page, text

    login(client, tenant.user.email)
    for path in ("/portal", "/portal/pay"):
        assert "Eastlea Garden Flats · Yuniti 3" in client.get(path).get_data(as_text=True), path

    client.get("/lang/ar")
    login(client, "owner@test.com")
    properties_page = client.get("/properties").get_data(as_text=True)
    for text in location_text:
        assert text in properties_page, f"{text!r} changed in Arabic"

    for code, table in TRANSLATIONS.items():
        for text in location_text:
            assert text not in table, f"{text!r} is a place name and must not have a {code} translation"


def test_language_menu_shows_the_current_language_and_lists_every_option(client):
    import re

    html = client.get("/lang/ar?next=/login", follow_redirects=True).get_data(as_text=True)
    summary = re.search(r"<summary[^>]*>(.*?)</summary>", html, re.S).group(1)
    assert "العربية" in summary and "English" not in summary
    options = re.search(r'<ul class="lang-options"[^>]*>(.*?)</ul>', html, re.S).group(1)
    assert re.findall(r'lang="(\w+)"', options) == ["en", "sn", "ar"]
    assert re.search(r'lang="ar" class="active" aria-current="true"', options)


@pytest.mark.parametrize("target", ["//evil.com", "/\\evil.com", "https://evil.com", "evil.com", "javascript:alert(1)"])
def test_language_switch_rejects_every_off_site_next(client, target):
    # Browsers treat "/\\evil.com" as "//evil.com", so a backslash must be refused too.
    resp = client.get("/lang/ar", query_string={"next": target})
    assert resp.status_code == 302
    assert "evil" not in resp.headers["Location"] and "javascript" not in resp.headers["Location"]


def test_safe_next_url_allows_only_same_site_paths():
    assert safe_next_url("/rent?x=1", "/d") == "/rent?x=1"
    for bad in ("//evil.com", "/\\evil.com", "https://evil.com", "evil.com", "", None):
        assert safe_next_url(bad, "/d") == "/d"


def test_login_next_cannot_leave_the_site(client, owner):
    resp = client.post("/login?next=/%5Cevil.com", data={"email": owner.email, "password": "password123"})
    assert resp.status_code == 302
    assert "evil.com" not in resp.headers["Location"]


def test_dates_keep_their_order_on_arabic_pages(client, owner, active_lease):
    login(client, owner.email)
    client.get("/lang/ar")
    page = client.get(f"/tenants/{active_lease.tenant_id}").get_data(as_text=True)
    # Wrapped in invisible Unicode isolates so right-to-left text cannot reorder them.
    assert f"\u2066{active_lease.start_date}\u2069" in page
    assert f"\u2066{active_lease.end_date}\u2069" in page
