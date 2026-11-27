import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import SRC, copy_library


@pytest.fixture()
def client(tmp_path, monkeypatch):
    root = tmp_path / "lib"
    copy_library(root)
    monkeypatch.setenv("EXAMGEN_AUTH", "0")  # accounts are covered in test_auth.py
    os.environ["EXAM_APP_HOME"] = str(root)
    from examgen.api import app
    return TestClient(app)


def test_health_and_courses(client):
    h = client.get("/api/health").json()
    assert h["latex"]
    cs = client.get("/api/courses").json()
    sn3 = next(c for c in cs if c["code"] == "203-SN3-RE")
    assert any(t["name"] == "MHS" for t in sn3["topics"])
    assert 1 in sn3["exams"]


def test_session_code(client):
    assert client.get("/api/session-code", params={"date": "2026-09-28"}).json()["code"] == "A26"
    assert client.get("/api/session-code", params={"date": "2027-02-01"}).json()["code"] == "H27"
    assert client.get("/api/session-code", params={"date": "2027-06-15"}).json()["code"] == "E27"


def test_question_roundtrip_and_test(client):
    payload = {
        "course": "203-SN3-RE", "topic": "MHS", "name": "api_test",
        "meta": {"title": "Test", "type": "developpement", "points": 20, "time_min": 10, "difficulty": 2,
                 "variables": {"k": {"type": "integer", "min": 10, "max": 50, "step": 5, "unit": "N/m"},
                               "m": {"type": "decimal", "min": 0.2, "max": 1.0, "step": 0.1, "unit": "kg"}},
                 "solution": {"mode": "auto", "parts": {"a": {"find": "w", "equation": "w**2 = k/m", "unit": "rad/s"}}}},
        "body": r"Un bloc de \qty{\v{m}}{kg} sur un ressort de \qty{\v{k}}{N/m}. Trouvez $\omega$.",
    }
    r = client.post("/api/questions/test", json={**payload, "draws": 2}).json()
    assert r["problems"] == [], r
    assert r["pdf"]
    assert client.get(f"/api/previews/{r['pdf']}.pdf").status_code == 200
    assert client.put("/api/questions", json=payload).status_code == 200
    got = client.get("/api/questions/203-SN3-RE/MHS/api_test").json()
    assert got["meta"]["solution"]["mode"] == "auto"
    assert client.put("/api/questions", json=payload).status_code == 409
    assert client.delete("/api/questions/203-SN3-RE/MHS/api_test").status_code == 200


def test_invalid_question_rejected(client):
    bad = {"course": "203-SN3-RE", "topic": "MHS", "name": "bad", "meta": {"title": "x", "type": "developpement",
           "points": 5, "time_min": 5, "difficulty": 2}, "body": r"\v{zz}"}
    r = client.put("/api/questions", json=bad)
    assert r.status_code == 422


def test_plan_and_export(client):
    req = {"course": "203-SN3-RE", "exam_number": 1, "date": "2026-09-28", "professor": "Jonathan Meloche-Gagnon",
           "duration_min": 120, "n_versions": 2, "seed": 5}
    p1 = client.post("/api/exams/plan", json=req).json()
    p2 = client.post("/api/exams/plan", json=req).json()
    assert p1["versions"] == p2["versions"]  # deterministic with a seed
    assert p1["session"] == "A26"
    slot0 = p1["versions"][0]["placed"][0]
    alts = client.post("/api/exams/alternatives", json={**req, "slot": slot0["slot"], "exclude": [slot0["question_id"]]}).json()
    assert alts and all(a["id"] != slot0["question_id"] for a in alts)
    locks = {p["slot"]: p["question_id"] for p in p1["versions"][0]["placed"]}
    locks[slot0["slot"]] = alts[0]["id"]
    p3 = client.post("/api/exams/plan", json={**req, "locks": locks}).json()
    assert p3["versions"][0]["placed"][0]["question_id"] == alts[0]["id"]
    ex = client.post("/api/exams/export", json={**req, "locks": locks}).json()
    names = [f["name"] for f in ex["files"]]
    assert "203-SN3-RE_Examen_1_A26_v1.pdf" in names and "203-SN3-RE_Examen_1_A26_v2_solution.pdf" in names
    assert client.get(ex["files"][0]["url"]).status_code == 200
    # Listing, ZIP download and deletion of a generated exam.
    listed = client.get("/api/exports").json()
    item = next(e for e in listed if e["name"] == ex["name"])
    assert item["course"] == ex["course"] == "203-SN3-RE" and item["n_versions"] == 2 and item["date"] == "2026-09-28"
    import io
    import zipfile
    for which, n in (("all", 4), ("exams", 2), ("solutions", 2)):
        r = client.get(f"/api/exports/{ex['course']}/{ex['name']}.zip", params={"which": which})
        assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
        assert len(zipfile.ZipFile(io.BytesIO(r.content)).namelist()) == n
    assert client.get(f"/api/exports/{ex['course']}/..%2F..%2Fconfig.yaml/x.pdf").status_code == 404
    assert client.delete(f"/api/exports/{ex['course']}/{ex['name']}").status_code == 200
    assert client.get(ex["files"][0]["url"]).status_code == 404
    assert all(e["name"] != ex["name"] for e in client.get("/api/exports").json())


def test_pair_pdfs():
    from examgen.api import _pair_pdfs
    names = ["X_v1.pdf", "X_v1_corrige.pdf", "X_v2.pdf", "Y_corrige.pdf"]
    assert _pair_pdfs(names, "_corrige") == [
        {"exam": "X_v1.pdf", "solution": "X_v1_corrige.pdf"}, {"exam": "X_v2.pdf", "solution": None},
        {"exam": None, "solution": "Y_corrige.pdf"}]
