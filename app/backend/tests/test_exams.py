"""Any number of exams per course, the final exam, custom titles and the printed course code."""
import datetime as dt
import os

import pytest
from fastapi.testclient import TestClient

from conftest import copy_library
from examgen.generate import ExamRequest, build_document, exam_basename, plan_exam
from examgen.library import FINAL, Library, exam_heading, exam_id

C = "203-SN3-RE"


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "lib"
    copy_library(r)
    return r


@pytest.fixture()
def client(root, monkeypatch):
    monkeypatch.setenv("EXAMGEN_AUTH", "0")
    os.environ["EXAM_APP_HOME"] = str(root)
    from examgen.api import app
    return TestClient(app)


def test_exam_id():
    assert exam_id(3) == 3 and exam_id("12") == 12 and exam_id("Final") == FINAL
    for bad in ("0", "-1", "abc", "../x", 0, True):
        with pytest.raises(ValueError):
            exam_id(bad)
    assert exam_heading(2) == r"Examen \#2" and exam_heading(FINAL) == "Examen final"
    assert exam_heading(2, "Examen de mi-session") == "Examen de mi-session"


def test_more_than_three_exams_and_final(client):
    for n in (4, 5, "final"):
        d = client.get(f"/api/exams/{C}/{n}").json()
        assert d["saved"] is False
        assert client.put(f"/api/exams/{C}/{n}", json=d).status_code == 200
    sn3 = next(c for c in client.get("/api/courses").json() if c["code"] == C)
    assert sn3["exams"][-3:] == [4, 5, "final"]  # numbers first, the final exam last

    assert client.get(f"/api/exams/{C}/nope").status_code == 400
    r = client.delete(f"/api/exams/{C}/5").json()
    assert r["deleted"] and 5 not in r["exams"]


def test_final_covers_every_topic(root):
    L = Library(root)
    fin = L.exam_def(C, FINAL)
    dev_topics = {t for t in L.topics(C) if L.questions(C, t, "developpement")}
    covered = {t for s in fin.sections if s.type == "developpement" for sl in s.slots for t in sl.topics}
    assert covered == dev_topics and fin.duration_min == 180
    assert len(dev_topics) > 4  # more than a regular exam's default


def test_title_roundtrip_and_cover(client, root):
    d = client.get(f"/api/exams/{C}/final").json()
    d["title"] = "Examen final & synthèse"
    client.put(f"/api/exams/{C}/final", json=d)
    sn3 = next(c for c in client.get("/api/courses").json() if c["code"] == C)
    assert sn3["exam_titles"] == {"final": "Examen final & synthèse"}

    L = Library(root)
    L.save_config({**L.config, "courses": {**L.config["courses"], C: {**L.config["courses"][C], "print_code": "203-NYC-05"}}})
    L = Library(root)
    req = ExamRequest.from_dict({"course": C, "exam_number": "final", "date": "2026-12-10", "professor": "X", "n_versions": 1})
    plan = plan_exam(L, req)
    tex, _ = build_document(L, plan, plan.versions[0], with_solutions=False)
    assert r"Examen final \& synthèse" in tex and "203-NYC-05" in tex and "#final" not in tex
    assert exam_basename(C, FINAL, dt.date(2026, 12, 10), 1, L.config) == "203-NYC-05_Examen_final_A26_v1"


def test_old_cover_templates_still_work(root):
    L = Library(root)
    (L.templates_dir).mkdir(parents=True, exist_ok=True)
    (L.templates_dir / "cover.tex").write_text(r"\textbf{<<exam_label>> \#<<exam_number>>} <<course>>", encoding="utf-8")
    for n, want in ((2, r"Examen \#2"), ("final", "Examen final")):
        req = ExamRequest.from_dict({"course": C, "exam_number": n, "date": "2026-12-10", "professor": "X", "n_versions": 1})
        plan = plan_exam(L, req)
        tex, _ = build_document(L, plan, plan.versions[0], with_solutions=False)
        assert rf"\textbf{{{want}}}" in tex
