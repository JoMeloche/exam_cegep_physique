"""FastAPI app: JSON API under /api and the built UI under /."""
from __future__ import annotations

import datetime as dt
import os
import platform
import random
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, values as V
from .generate import (ExamRequest, alternatives, exam_basename, export_dir, export_exam, plan_exam,
                       preview_question, session_code, load_usage)
from .latex import LatexError, find_engine
from .library import ExamDef, Library
from .model import NAME_RE, VREF_RE, Question, QuestionError
from .solve import SolveError, solve_parts
from .validate import validate_question

app = FastAPI(title="Générateur d'examens", version=__version__)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

_PREVIEWS = Path(tempfile.gettempdir()) / "examgen-previews"
_PREVIEWS.mkdir(exist_ok=True)


def lib() -> Library:
    root = os.environ.get("EXAM_APP_HOME")
    if not hasattr(app.state, "lib") or (root and Path(root).expanduser() != app.state.lib.root):
        app.state.lib = Library(root).ensure()
    app.state.lib.reload()
    return app.state.lib


def desktop_mode() -> bool:
    return os.environ.get("EXAMGEN_DESKTOP") == "1"


@app.exception_handler(LatexError)
async def _latex_error(_, exc: LatexError):
    return JSONResponse(status_code=422, content={"detail": str(exc), "log": exc.log_excerpt,
                                                  "question_id": exc.question_id})


@app.exception_handler(QuestionError)
async def _question_error(_, exc: QuestionError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# ------------------------------------------------------------------ meta
@app.get("/api/health")
def health() -> dict[str, Any]:
    L = lib()
    cfg = L.config.get("latex") or {}
    return {"version": __version__, "root": str(L.root), "desktop": desktop_mode(),
            "latex": find_engine(cfg.get("engine", "pdflatex"), cfg.get("path", "")),
            "platform": platform.system()}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return lib().config


@app.put("/api/config")
def put_config(cfg: dict[str, Any] = Body(...)) -> dict[str, Any]:
    L = lib()
    merged = {**L.config, **cfg}
    L.save_config(merged)
    return merged


@app.get("/api/session-code")
def get_session_code(date: str) -> dict[str, str]:
    return {"code": session_code(dt.date.fromisoformat(date[:10]))}


@app.get("/api/courses")
def courses() -> list[dict[str, Any]]:
    L = lib()
    cfg = L.config
    out = []
    for c in L.courses():
        info = (cfg.get("courses") or {}).get(c, {})
        topics = []
        for t in L.topics(c):
            qs = L.questions(c, t)
            topics.append({"name": t, "label": (cfg.get("topics") or {}).get(t, t.replace("_", " ")),
                           "n_dev": sum(q.type == "developpement" for q in qs),
                           "n_concept": sum(q.type == "conceptuel" for q in qs)})
        out.append({"code": c, **info, "topics": topics, "exams": L.exam_numbers(c)})
    return out


# ------------------------------------------------------------------ questions
def _full(q: Question) -> dict[str, Any]:
    usage = load_usage(lib()).get(q.id, [])
    return {**q.summary(), "meta": q.meta_dict(), "body": q.body, "solution_tex": q.solution_tex,
            "problems": q.problems(), "usage": usage}


@app.get("/api/questions")
def list_questions(course: str | None = None, topic: str | None = None, type: str | None = None,
                   q: str | None = None) -> dict[str, Any]:
    L = lib()
    usage = load_usage(L)
    items = []
    needle = (q or "").lower()
    for qq in L.questions(course, topic, type):
        if needle and needle not in (qq.title + " " + qq.body + " " + qq.name).lower():
            continue
        s = qq.summary()
        u = usage.get(qq.id, [])
        s["times_used"] = len(u)
        s["last_used"] = max((x.get("date", "") for x in u), default="")
        txt = re.sub(r"\\v\{(\w+)\}", r"\1", qq.clean_body)
        txt = re.sub(r"\\(begin|end)\{[^}]*\}(\[[^\]]*\])?|\\\\(\[[^\]]*\])?|\\(rule|hrulefill|vfill|vspace|includegraphics)(\[[^\]]*\])?(\{[^}]*\})*", " ", txt)
        txt = re.sub(r"Justification\s*:|Réponse\s*:", " ", txt)
        s["excerpt"] = re.sub(r"\s+", " ", re.sub(r"\\[a-zA-Z]+|[{}$\\]", " ", txt))[:180].strip()
        s["answer"] = qq.answer
        items.append(s)
    items.sort(key=lambda x: (x["course"], x["topic"], x["type"], x["name"]))
    return {"items": items, "errors": L.load_errors}


@app.get("/api/questions/{qid:path}")
def get_question(qid: str) -> dict[str, Any]:
    try:
        return _full(lib().get(qid))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


def _question_from_payload(p: dict[str, Any]) -> Question:
    course, topic, name = p.get("course", ""), p.get("topic", ""), p.get("name", "")
    for label, v in (("cours", course), ("thème", topic), ("nom", name)):
        if not v or not NAME_RE.match(v):
            raise QuestionError(f"{label} invalide : utilisez lettres, chiffres, - et _ (sans accents ni espaces)")
    return Question.from_dict(f"{course}/{topic}/{name}", p.get("meta") or {}, p.get("body", ""),
                              solution_tex=p.get("solution_tex", ""))


@app.put("/api/questions")
def save_question(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    L = lib()
    q = _question_from_payload(payload)
    old_id = payload.get("original_id")
    try:
        existing = L.get(q.id)
        q.history = existing.history
    except KeyError:
        existing = None
    if existing is not None and old_id != q.id and not payload.get("overwrite"):
        raise HTTPException(409, f"Une question {q.id} existe déjà")
    errs = q.problems()
    if errs and not payload.get("force"):
        raise HTTPException(422, {"detail": "Question invalide", "problems": errs})
    q.extra.pop("needs_review", None) if payload.get("reviewed") else None
    L.save_question(q)
    if old_id and old_id != q.id:
        try:
            L.delete_question(old_id)
        except KeyError:
            pass
    return _full(L.get(q.id))


@app.delete("/api/questions/{qid:path}")
def delete_question(qid: str) -> dict[str, str]:
    try:
        lib().delete_question(qid)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"deleted": qid}


@app.post("/api/questions/detect-variables")
def detect_variables(payload: dict[str, Any] = Body(...)) -> dict[str, list[str]]:
    names: list[str] = []
    for text in (payload.get("body", ""), payload.get("solution_tex", "")):
        for _, n in VREF_RE.findall(text or ""):
            if n and n not in names:
                names.append(n)
    return {"variables": names}


@app.post("/api/questions/test")
def test_question(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Static checks + n random draws + compile. Returns problems and a preview PDF id."""
    L = lib()
    q = _question_from_payload(payload)
    n = int(payload.get("draws", 5))
    problems = q.problems()
    result: dict[str, Any] = {"problems": problems, "pdf": None, "draws": [], "answers": []}
    if problems:
        return result
    pid = uuid.uuid4().hex
    wd = _PREVIEWS / pid
    try:
        pdf, draws = preview_question(L, q, seed=random.randrange(1, 10**6), n=n, workdir=wd)
        result["pdf"] = pid
        result["draws"] = [{k: (V.fmt_plain(v) if not isinstance(v, str) else v) for k, v in d.items()} for d in draws]
        if q.parts:
            for d in draws:
                try:
                    result["answers"].append([{"key": r.key, "name": r.name, "value": V.fmt_sig(r.value, 4),
                                               "unit": r.unit} for r in solve_parts(q, d, with_latex=False)])
                except (SolveError, Exception) as exc:  # noqa: BLE001
                    result["problems"].append(f"solution : {exc}")
                    break
    except V.DrawError as exc:
        result["problems"].append(str(exc))
    except LatexError as exc:
        result["problems"].append(str(exc))
        result["log"] = exc.log_excerpt
    return result


@app.get("/api/previews/{pid}.pdf")
def get_preview(pid: str):
    if not re.fullmatch(r"[0-9a-f]{32}", pid):
        raise HTTPException(404)
    p = _PREVIEWS / pid / "apercu.pdf"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="application/pdf")


@app.post("/api/validate")
def validate_all(course: str | None = None, compile: bool = False) -> dict[str, list[str]]:
    L = lib()
    return {q.id: validate_question(L, q, compile_check=compile) for q in L.questions(course)}


# ------------------------------------------------------------------ figures
@app.get("/api/figures")
def list_figures() -> list[str]:
    d = lib().figures_dir
    return sorted(p.name for p in d.iterdir() if p.is_file()) if d.exists() else []


@app.post("/api/figures")
async def upload_figure(file: UploadFile = File(...)) -> dict[str, str]:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(file.filename or "figure.png").name)
    if not re.search(r"\.(png|jpe?g|pdf|eps)$", name, re.I):
        raise HTTPException(400, "Formats acceptés : png, jpg, pdf, eps")
    dest = lib().figures_dir / name
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    return {"name": name}


@app.get("/api/figures/{name}")
def get_figure(name: str):
    p = lib().figures_dir / Path(name).name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


# ------------------------------------------------------------------ exams
@app.get("/api/exams/{course}/{number}")
def get_exam_def(course: str, number: int) -> dict[str, Any]:
    L = lib()
    return {**L.exam_def(course, number).to_dict(), "saved": L.exam_path(course, number).exists()}


@app.put("/api/exams/{course}/{number}")
def put_exam_def(course: str, number: int, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    L = lib()
    ed = ExamDef.from_dict({**payload, "course": course, "number": number})
    L.save_exam_def(ed)
    return ed.to_dict()


@app.post("/api/exams/plan")
def plan(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    L = lib()
    req = ExamRequest.from_dict(payload)
    p = plan_exam(L, req)
    out = p.to_dict(L)
    out["session"] = session_code(req.date)
    out["export_dir"] = str(export_dir(L, req))
    return out


@app.post("/api/exams/alternatives")
def exam_alternatives(payload: dict[str, Any] = Body(...)) -> list[dict[str, Any]]:
    L = lib()
    req = ExamRequest.from_dict(payload)
    ed = req.exam_def or L.exam_def(req.course, req.exam_number)
    exclude = set(payload.get("exclude") or [])
    return [q.summary() for q in alternatives(L, ed, req.course, payload["slot"], exclude)]


@app.post("/api/exams/export")
def export(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    L = lib()
    req = ExamRequest.from_dict(payload)
    p = plan_exam(L, req)
    res = export_exam(L, p, record_usage=bool(payload.get("record_usage", True)))
    rel = res.folder.relative_to(L.exports_dir)
    return {"folder": str(res.folder), "files": [{"name": f.name, "url": f"/api/exports/{rel.as_posix()}/{f.name}",
                                                  "path": str(f)} for f in res.files],
            "warnings": res.warnings, "seed": p.seed}


@app.get("/api/exports")
def list_exports() -> list[dict[str, Any]]:
    L = lib()
    out = []
    if L.exports_dir.exists():
        for d in sorted(L.exports_dir.glob("*/*"), key=lambda p: p.stat().st_mtime, reverse=True):
            if d.is_dir():
                pdfs = sorted(f.name for f in d.glob("*.pdf"))
                out.append({"course": d.parent.name, "name": d.name, "files": pdfs,
                            "folder": str(d), "modified": dt.datetime.fromtimestamp(d.stat().st_mtime).isoformat()})
    return out


@app.get("/api/exports/{course}/{folder}/{name}")
def get_export(course: str, folder: str, name: str):
    L = lib()
    p = (L.exports_dir / course / folder / name).resolve()
    if not str(p).startswith(str(L.exports_dir.resolve())) or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="application/pdf", filename=p.name if p.suffix == ".pdf" else None)


@app.post("/api/open")
def open_path(payload: dict[str, str] = Body(...)) -> dict[str, bool]:
    """Desktop only: open a file or folder with the OS."""
    if not desktop_mode():
        raise HTTPException(403, "Disponible seulement dans l'application de bureau")
    L = lib()
    p = Path(payload["path"]).resolve()
    if not str(p).startswith(str(L.root.resolve())):
        raise HTTPException(403)
    if payload.get("reveal") and p.is_file():
        p = p.parent
    if platform.system() == "Windows":
        os.startfile(str(p))  # type: ignore[attr-defined]  # noqa: S606
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(p)])  # noqa: S603,S607
    else:
        subprocess.Popen(["xdg-open", str(p)])  # noqa: S603,S607
    return {"ok": True}


# ------------------------------------------------------------------ static UI
_STATIC = Path(os.environ.get("EXAMGEN_STATIC", Path(__file__).parent / "static"))
if (_STATIC / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_STATIC / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        f = _STATIC / full_path
        if full_path and f.is_file() and _STATIC in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(_STATIC / "index.html")

_ = exam_basename  # re-exported for clients
