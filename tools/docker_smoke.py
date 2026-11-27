"""Smoke test of a running web app (the Docker image in CI): sign in, export one exam, download it.

    python tools/docker_smoke.py http://127.0.0.1:8765 admin@example.org 'password'
"""
from __future__ import annotations

import http.cookiejar
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile

base, email, password = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def csrf() -> str:
    return next((c.value for c in jar if c.name == "examgen_csrf"), "")


def call(method: str, path: str, body: dict | None = None, raw: bool = False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Origin", base)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if method not in ("GET", "HEAD"):
        req.add_header("X-CSRF-Token", csrf())
    with opener.open(req, timeout=600) as r:
        content = r.read()
        return content if raw else json.loads(content or b"null")


for _ in range(90):  # the container needs a few seconds to start
    try:
        call("GET", "/api/health")
        break
    except (urllib.error.URLError, ConnectionError):
        time.sleep(2)
else:
    sys.exit("the app never answered on /api/health")

call("GET", "/api/auth/state")
call("POST", "/api/auth/login", {"email": email, "password": password})
state = call("GET", "/api/auth/state")
assert state["user"] and state["user"]["role"] == "admin", state
health = call("GET", "/api/health")
assert health["latex"], f"no LaTeX in the image: {health}"
courses = {c["code"]: c for c in call("GET", "/api/courses")}
assert len(courses) >= 5 and all(courses[c]["topics"] for c in courses), sorted(courses)
print(f"signed in, {len(courses)} courses, LaTeX at {health['latex']}")

t0 = time.time()
res = call("POST", "/api/exams/export", {"course": "203-SN3-RE", "exam_number": 1, "date": "2026-09-28",
                                         "professor": "Test CI", "duration_min": 120, "n_versions": 1, "seed": 1})
names = [f["name"] for f in res["files"]]
assert names == ["203-SN3-RE_Examen_1_A26_v1.pdf", "203-SN3-RE_Examen_1_A26_v1_solution.pdf"], names
pdf = call("GET", res["files"][0]["url"], raw=True)
assert pdf[:5] == b"%PDF-" and len(pdf) > 20_000, len(pdf)
z = zipfile.ZipFile(io.BytesIO(call("GET", f"/api/exports/{res['course']}/{res['name']}.zip", raw=True)))
assert sorted(z.namelist()) == sorted(names), z.namelist()
print(f"exported {len(names)} PDFs in {time.time() - t0:.1f} s; ZIP ok")
