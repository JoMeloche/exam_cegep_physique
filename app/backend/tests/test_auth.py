"""Accounts: sign-up with a reason, admin approval, sessions, CSRF, rate limits, per-user banks, sharing."""
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SRC = Path(os.environ.get("EXAMGEN_TEST_LIB", "/tmp/apilib"))
ADMIN = ("admin@cegep.test", "admin-password-123")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    root = tmp_path / "data"
    shutil.copytree(SRC, root)
    monkeypatch.setenv("EXAM_APP_HOME", str(root))
    monkeypatch.setenv("EXAMGEN_AUTH", "1")
    monkeypatch.delenv("EXAMGEN_DESKTOP", raising=False)
    monkeypatch.setenv("EXAMGEN_SEED", str(SRC))
    monkeypatch.setenv("EXAMGEN_ADMIN_EMAIL", ADMIN[0])
    monkeypatch.setenv("EXAMGEN_ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.delenv("EXAMGEN_LIBRARY_MODE", raising=False)
    from examgen import auth
    auth.limiter.reset()
    from examgen.api import app
    return root, app


def new_client(app) -> TestClient:
    c = TestClient(app)
    c.get("/api/auth/state")  # gets the anonymous CSRF cookie
    return c


def csrf(c: TestClient) -> dict:
    return {"X-CSRF-Token": c.cookies.get("examgen_csrf") or ""}


def post(c, url, json=None):
    return c.post(url, json=json if json is not None else {}, headers=csrf(c))


def login(c, email, pw):
    return post(c, "/api/auth/login", {"email": email, "password": pw})


def signup(c, name, email, pw="a-good-password-1", reason="Je suis enseignant de physique au cégep."):
    return post(c, "/api/auth/signup", {"name": name, "email": email, "password": pw, "reason": reason})


def test_api_requires_login(env):
    _, app = env
    c = new_client(app)
    assert c.get("/api/courses").status_code == 401
    assert c.get("/api/questions").status_code == 401
    assert c.get("/api/figures/x.png").status_code == 401
    h = c.get("/api/health").json()
    assert h["auth"] and "root" not in h
    st = c.get("/api/auth/state").json()
    assert st["enabled"] and st["user"] is None and not st["needs_setup"]


def test_csrf_and_origin(env):
    _, app = env
    c = new_client(app)
    r = c.post("/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
    assert r.status_code == 403  # no CSRF header
    r = c.post("/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]},
               headers={**csrf(c), "Origin": "https://evil.example"})
    assert r.status_code == 403
    assert login(c, *ADMIN).status_code == 200
    # once signed in, the token is bound to the session
    assert c.put("/api/config", json={"school": "X"}, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert c.put("/api/config", json={"school": "X"}, headers=csrf(c)).status_code == 200


def test_session_cookie_flags(env):
    _, app = env
    c = new_client(app)
    r = login(c, *ADMIN)
    cookie = [v for k, v in r.headers.multi_items() if k == "set-cookie" and v.startswith("examgen_session=")][0]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert r.headers["x-frame-options"] == "SAMEORIGIN"


def test_signup_approval_flow(env):
    root, app = env
    u = new_client(app)
    assert signup(u, "Ana", "ana@cegep.test", reason="trop court").status_code == 400
    assert signup(u, "Ana", "ana@cegep.test", pw="short").status_code == 400
    assert signup(u, "Ana", "ana@cegep.test").status_code == 202
    # same answer for an address already taken
    assert signup(u, "Ana2", "ana@cegep.test").status_code == 202
    r = login(u, "ana@cegep.test", "a-good-password-1")
    assert r.status_code == 403 and "attente" in r.json()["detail"]
    assert login(u, "ana@cegep.test", "wrong-password!").status_code == 401

    a = new_client(app)
    login(a, *ADMIN)
    lst = a.get("/api/admin/users", params={"status": "pending"}).json()
    ana = next(x for x in lst["users"] if x["email"] == "ana@cegep.test")
    assert ana["reason"].startswith("Je suis")
    assert a.get("/api/auth/state").json()["pending"] == 1
    # a normal user can't reach the admin API
    assert u.get("/api/admin/users").status_code == 401
    assert post(a, f"/api/admin/users/{ana['id']}/approve").status_code == 200
    assert login(u, "ana@cegep.test", "a-good-password-1").status_code == 200
    assert u.get("/api/admin/users").status_code == 403
    # her own bank, seeded from the starter bank, separate from the admin's
    assert (root / "users" / str(ana["id"]) / "questions").is_dir()
    assert u.get("/api/questions").json()["items"]
    h = u.get("/api/health").json()
    assert h["root"].endswith(f"users/{ana['id']}")
    # disabling kills her session
    assert post(a, f"/api/admin/users/{ana['id']}/disable").status_code == 200
    assert u.get("/api/courses").status_code == 401


def test_reject_and_last_admin(env):
    _, app = env
    u = new_client(app)
    signup(u, "Bob", "bob@cegep.test")
    a = new_client(app)
    login(a, *ADMIN)
    bob = a.get("/api/admin/users", params={"status": "pending"}).json()["users"][0]
    assert post(a, f"/api/admin/users/{bob['id']}/reject", {"note": "Pas un enseignant"}).status_code == 200
    r = login(u, "bob@cegep.test", "a-good-password-1")
    assert r.status_code == 403 and "Pas un enseignant" in r.json()["detail"]
    me = a.get("/api/auth/state").json()["user"]
    assert post(a, f"/api/admin/users/{me['id']}/disable").status_code == 400
    assert post(a, f"/api/admin/users/{me['id']}/make-user").status_code == 400


def test_login_rate_limit(env):
    _, app = env
    c = new_client(app)
    codes = [login(c, ADMIN[0], f"wrong-{i}-password").status_code for i in range(9)]
    assert codes[:8] == [401] * 8 and codes[8] == 429
    assert login(c, *ADMIN).status_code == 429  # locked for this account for a while


def test_signup_rate_limit(env):
    _, app = env
    c = new_client(app)
    codes = [signup(c, f"P{i}", f"p{i}@cegep.test").status_code for i in range(6)]
    assert codes[:5] == [202] * 5 and codes[5] == 429


def test_password_change_and_reset(env):
    _, app = env
    a = new_client(app)
    login(a, *ADMIN)
    signup(new_client(app), "Cy", "cy@cegep.test")
    cy = a.get("/api/admin/users", params={"status": "pending"}).json()["users"][0]
    post(a, f"/api/admin/users/{cy['id']}/approve")
    temp = post(a, f"/api/admin/users/{cy['id']}/reset-password").json()["temporary_password"]
    u = new_client(app)
    assert login(u, "cy@cegep.test", temp).status_code == 200
    r = post(u, "/api/auth/password", {"current_password": temp, "new_password": "brand-new-password-9"})
    assert r.status_code == 200
    assert post(u, "/api/auth/logout").status_code == 200
    assert u.get("/api/courses").status_code == 401
    assert login(u, "cy@cegep.test", "brand-new-password-9").status_code == 200


def test_setup_code_flow(env, monkeypatch, tmp_path):
    monkeypatch.delenv("EXAMGEN_ADMIN_EMAIL")
    monkeypatch.delenv("EXAMGEN_ADMIN_PASSWORD")
    monkeypatch.setenv("EXAMGEN_SETUP_TOKEN", "code-for-tests-1234")
    monkeypatch.setenv("EXAMGEN_AUTH_DB", str(tmp_path / "fresh.sqlite3"))
    _, app = env
    c = new_client(app)
    assert c.get("/api/auth/state").json()["needs_setup"]
    body = {"token": "nope", "name": "Jo", "email": "jo@cegep.test", "password": "jo-password-12345"}
    assert post(c, "/api/auth/setup", body).status_code == 403
    r = post(c, "/api/auth/setup", {**body, "token": "code-for-tests-1234"})
    assert r.status_code == 201
    assert c.get("/api/auth/state").json()["user"]["role"] == "admin"
    assert post(new_client(app), "/api/auth/setup", {**body, "token": "code-for-tests-1234"}).status_code == 409


def test_latex_settings_locked(env):
    _, app = env
    from examgen import latex
    latex.RESTRICTED = True
    try:
        a = new_client(app)
        login(a, *ADMIN)
        a.put("/api/config", json={"latex": {"path": "/bin/sh", "engine": "sh"}}, headers=csrf(a))
        assert a.get("/api/config").json()["latex"]["path"] == ""
    finally:
        latex.RESTRICTED = False


def _approved(app, a, name, email):
    signup(new_client(app), name, email)
    uid = next(x["id"] for x in a.get("/api/admin/users").json()["users"] if x["email"] == email)
    post(a, f"/api/admin/users/{uid}/approve")
    c = new_client(app)
    assert login(c, email, "a-good-password-1").status_code == 200
    return c, uid


def test_sharing(env):
    root, app = env
    a = new_client(app)
    login(a, *ADMIN)
    ana, ana_id = _approved(app, a, "Ana", "ana@cegep.test")
    bob, bob_id = _approved(app, a, "Bob", "bob@cegep.test")
    # Ana writes a new question; nobody else sees it
    q = {"course": "203-SN3-RE", "topic": "MHS", "name": "ana_ressort",
         "meta": {"title": "Ressort d'Ana", "type": "developpement", "points": 20, "time_min": 10, "difficulty": 2,
                  "variables": {"k": {"type": "integer", "min": 10, "max": 50, "step": 5, "unit": "N/m"}},
                  "solution": {"mode": "none"}},
         "body": r"Un ressort de \qty{\v{k}}{N/m}."}
    assert ana.put("/api/questions", json=q, headers=csrf(ana)).status_code == 200
    assert not bob.get("/api/questions", params={"scope": "shared"}).json()["items"]
    # share it with Bob only
    users = ana.get("/api/shares").json()["users"]
    assert {u["id"] for u in users} >= {bob_id}
    r = ana.put("/api/shares", json={"target": "203-SN3-RE/MHS/ana_ressort", "audience": "users", "user_ids": [bob_id]},
                headers=csrf(ana))
    assert r.status_code == 200, r.text
    shared = bob.get("/api/questions", params={"scope": "shared"}).json()["items"]
    assert [s["title"] for s in shared] == ["Ressort d'Ana"] and shared[0]["shared_by"] == "Ana"
    sid = shared[0]["id"]
    # starter-bank copies are not duplicated even when the whole bank is shared
    ana.put("/api/shares", json={"target": "*", "audience": "all", "user_ids": []}, headers=csrf(ana))
    assert len(bob.get("/api/questions", params={"scope": "shared"}).json()["items"]) == 1
    assert a.get("/api/questions", params={"scope": "shared"}).json()["items"]
    # read-only for Bob; he can copy it into his own bank
    assert bob.delete(f"/api/questions/{sid}", headers=csrf(bob)).status_code == 403
    assert bob.put("/api/questions", json={**q, "name": sid.split("/")[-1]}, headers=csrf(bob)).status_code == 403
    assert bob.get(f"/api/questions/{sid}").json()["read_only"]
    new_id = post(bob, "/api/shares/copy", {"id": sid}).json()["id"]
    assert new_id == "203-SN3-RE/MHS/ana_ressort"
    assert (root / "users" / str(bob_id) / "questions/203-SN3-RE/MHS/ana_ressort.yaml").exists()
    # exam planning can draw from shared questions only when asked
    base = {"course": "203-SN3-RE", "exam_number": 1, "date": "2026-09-28", "professor": "X", "n_versions": 1, "seed": 3}
    alts = bob.post("/api/exams/alternatives", json={**base, "slot": "0.0.0", "exclude": [], "include_shared": True},
                    headers=csrf(bob)).json()
    assert isinstance(alts, list)
    # unsharing removes access
    for s in ana.get("/api/shares").json()["shares"]:
        assert ana.delete(f"/api/shares/{s['id']}", headers=csrf(ana)).status_code == 200
    assert not bob.get("/api/questions", params={"scope": "shared"}).json()["items"]


def test_shared_library_mode(env, monkeypatch):
    monkeypatch.setenv("EXAMGEN_LIBRARY_MODE", "shared")
    root, app = env
    a = new_client(app)
    login(a, *ADMIN)
    c, _ = _approved(app, a, "Dee", "dee@cegep.test")
    assert c.get("/api/health").json()["root"] == str(root)
    assert c.get("/api/shares").status_code == 404


def test_desktop_mode_has_no_login(env, monkeypatch):
    monkeypatch.setenv("EXAMGEN_DESKTOP", "1")
    _, app = env
    c = TestClient(app)
    assert c.get("/api/courses").status_code == 200
    assert c.put("/api/config", json={"school": "X"}).status_code == 200  # curl-style, no Origin
    assert c.put("/api/config", json={"school": "X"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert not c.get("/api/auth/state").json()["enabled"]
