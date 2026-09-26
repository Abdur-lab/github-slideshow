from backend.i18n import SHONA
from tests.conftest import login


def test_english_is_the_default(client):
    resp = client.get("/login")
    assert b'<html lang="en">' in resp.data
    assert b"Forgot your password?" in resp.data


def test_switching_to_shona_translates_the_login_page(client):
    resp = client.get("/lang/sn?next=/login", follow_redirects=True)
    assert b'<html lang="sn">' in resp.data
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
    assert b'<html lang="en">' in resp.data


def test_language_switch_does_not_open_redirect(client):
    resp = client.get("/lang/sn?next=https://evil.example.com/")
    assert resp.status_code == 302
    assert "evil.example.com" not in resp.headers["Location"]


def test_every_shona_entry_keeps_its_placeholders():
    import re

    for english, shona in SHONA.items():
        assert set(re.findall(r"{(\w+)}", english)) == set(re.findall(r"{(\w+)}", shona)), english
