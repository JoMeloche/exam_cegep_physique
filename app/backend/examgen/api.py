"""FastAPI app: JSON API under /api and the built UI under /."""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import random
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, auth, latex as LX, sharing, values as V
from .auth_routes import AuthMiddleware, router as auth_router
from .generate import (ExamRequest, alternatives, exam_basename, export_dir, export_exam, plan_exam,
                       preview_question, session_code, load_usage)
from .latex import LatexError, find_engine
from .library import ExamDef, Library
from .model import NAME_RE, VREF_RE, Question, QuestionError
from .solve import SolveError, solve_parts
from .validate import validate_question

@asynccontextmanager
async def _lifespan(_app):
    LX.RESTRICTED = auth.enabled()
    if auth.enabled():
        auth.store().purge_expired()  # also creates the first admin or prints the setup code
    yield


app = FastAPI(title="Générateur d'examens", version=__version__, lifespan=_lifespan,
              docs_url=None if auth.enabled() else "/docs", redoc_url=None,
              openapi_url=None if auth.enabled() else "/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.add_middleware(AuthMiddleware)
app.include_router(auth_router)

_PREVIEWS = Path(tempfile.gettempdir()) / "examgen-previews"
_PREVIEWS.mkdir(exist_ok=True)
MAX_UPLOAD = 20 * 1024 * 1024
_libs: dict[Path, Library] = {}
_libs_lock = threading.Lock()


def own_lib() -> Library:
    """The library of the signed-in teacher (web app), or the single local library (desktop, auth off)."""
    user = auth.current_user.get() if auth.enabled() else None
    root = auth.library_root(user) if user else Path(os.environ.get("EXAM_APP_HOME") or Library().root).expanduser()
    with _libs_lock:
        L = _libs.get(root)
        if L is None:
            if user:
                auth.provision_library(user)
            L = _libs[root] = Library(root).ensure()
    L.refresh()
    return L


def sharing_on() -> bool:
    return auth.enabled() and auth.library_mode() == "per-user" and auth.current_user.get() is not None


def lib(include_shared: bool = False) -> Library:
    """Own library, or own + questions colleagues shared with this teacher."""
    L = own_lib()
    if include_shared and sharing_on():
        return sharing.SharedLibrary(L, auth.current_user.get())  # type: ignore[arg-type]
    return L


def desktop_mode() -> bool:
    return auth.desktop_mode()


def _user_key() -> str:
    u = auth.current_user.get()
    return f"u{u.id}" if u else "local"


@app.exception_handler(auth.AuthError)
async def _auth_error(_, exc: auth.AuthError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.detail}, headers=exc.headers)


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
    if auth.enabled() and auth.current_user.get() is None:
        return {"version": __version__, "desktop": False, "auth": True}
    L = lib()
    cfg = L.config.get("latex") or {}
    return {"version": __version__, "root": str(L.root), "desktop": desktop_mode(), "auth": auth.enabled(),
            "latex_locked": LX.RESTRICTED,
            "latex": find_engine(cfg.get("engine", "pdflatex"), cfg.get("path", "")),
            "platform": platform.system()}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return lib().config


@app.put("/api/config")
def put_config(cfg: dict[str, Any] = Body(...)) -> dict[str, Any]:
    L = lib()
    if LX.RESTRICTED:
        cfg = {k: v for k, v in cfg.items() if k != "latex"}  # the server decides which TeX runs
    merged = {**L.config, **cfg}
    L.save_config(merged)
    return L.config


@app.get("/api/session-code")
def get_session_code(date: str) -> dict[str, str]:
    return {"code": session_code(dt.date.fromisoformat(date[:10]), lib().config.get("sessions"))}


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
def _share_info(L: Library, qid: str) -> dict[str, Any]:
    """Who shared it (questions from colleagues), or how I share it (my own questions)."""
    if isinstance(L, sharing.SharedLibrary) and qid in L.origins:
        o = L.origins[qid]
        return {"shared_by": o.owner_name, "read_only": True}
    return {}


def _my_share_map() -> dict[str, str]:
    if not sharing_on():
        return {}
    return {s["target"]: s["audience"] for s in sharing.my_shares(auth.current_user.get())}  # type: ignore[arg-type]


def _full(q: Question, L: Library | None = None) -> dict[str, Any]:
    L = L or lib()
    usage = load_usage(L).get(q.id, [])
    shares = _my_share_map()
    return {**q.summary(), "meta": q.meta_dict(), "body": q.body, "solution_tex": q.solution_tex,
            "problems": q.problems(), "usage": usage, **_share_info(L, q.id),
            "my_share": shares.get(q.id) or shares.get("*")}


@app.get("/api/questions")
def list_questions(course: str | None = None, topic: str | None = None, type: str | None = None,
                   q: str | None = None, scope: str = "mine") -> dict[str, Any]:
    """scope: mine (default) | shared (colleagues' questions shared with me) | all."""
    L = lib(include_shared=scope in {"shared", "all"})
    usage = load_usage(L)
    shares = _my_share_map()
    items = []
    needle = (q or "").lower()
    for qq in L.questions(course, topic, type):
        if scope == "shared" and not _share_info(L, qq.id):
            continue
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
        s.update(_share_info(L, qq.id))
        if not s.get("shared_by"):
            s["my_share"] = shares.get(qq.id) or shares.get("*")
        items.append(s)
    items.sort(key=lambda x: (x["course"], x["topic"], x["type"], x["name"]))
    return {"items": items, "errors": L.load_errors}


@app.get("/api/questions/{qid:path}")
def get_question(qid: str) -> dict[str, Any]:
    try:
        L = lib(include_shared=sharing.split_shared_id(qid) is not None)
        return _full(L.get(qid), L)
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
    if sharing_on() and sharing.split_shared_id(q.id):
        raise HTTPException(403, "Question partagée : copiez-la dans votre banque pour la modifier.")
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
    if old_id and old_id != q.id and not (sharing_on() and sharing.split_shared_id(old_id)):
        try:
            L.delete_question(old_id)
        except KeyError:
            pass
    return _full(L.get(q.id))


@app.delete("/api/questions/{qid:path}")
def delete_question(qid: str) -> dict[str, str]:
    if sharing_on() and sharing.split_shared_id(qid):
        raise HTTPException(403, "Question partagée : seul son auteur peut la supprimer.")
    try:
        lib().delete_question(qid)
        if sharing_on():
            sharing.unshare_question(auth.current_user.get(), qid)  # type: ignore[arg-type]
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
    q = _question_from_payload(payload)
    L = lib(include_shared=sharing.split_shared_id(q.id) is not None)
    n = max(1, min(int(payload.get("draws", 5)), 20))
    problems = q.problems()
    result: dict[str, Any] = {"problems": problems, "pdf": None, "draws": [], "answers": []}
    if problems:
        return result
    pid = uuid.uuid4().hex
    wd = _PREVIEWS / _user_key() / pid
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
    p = _PREVIEWS / _user_key() / pid / "apercu.pdf"
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
    tmp = dest.with_name(f".{name}.{uuid.uuid4().hex}.part")
    size = 0
    try:
        with tmp.open("wb") as fh:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "Fichier trop volumineux (20 Mo au maximum)")
                fh.write(chunk)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return {"name": name}


@app.get("/api/figures/{name}")
def get_figure(name: str):
    p = lib().figures_dir / Path(name).name
    if not p.exists() and sharing_on():  # a figure of a question a colleague shared with me
        view = lib(include_shared=True)
        view.questions()
        for o in view.origins.values():  # type: ignore[attr-defined]
            if Path(name).name in {Path(f).name for f in o.library.get(o.original_id).figures}:
                p = o.library.figures_dir / Path(name).name
                break
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
    L = lib(include_shared=bool(payload.get("include_shared")))
    req = ExamRequest.from_dict(payload)
    p = plan_exam(L, req)
    out = p.to_dict(L)
    for v in out["versions"]:
        for item in v["placed"]:
            item.update(_share_info(L, item["question_id"]))
    out["session"] = session_code(req.date, L.config.get("sessions"))
    out["export_dir"] = str(export_dir(L, req))
    return out


@app.post("/api/exams/alternatives")
def exam_alternatives(payload: dict[str, Any] = Body(...)) -> list[dict[str, Any]]:
    L = lib(include_shared=bool(payload.get("include_shared")))
    req = ExamRequest.from_dict(payload)
    ed = req.exam_def or L.exam_def(req.course, req.exam_number)
    exclude = set(payload.get("exclude") or [])
    return [{**q.summary(), **_share_info(L, q.id)} for q in alternatives(L, ed, req.course, payload["slot"], exclude)]


@app.post("/api/exams/export")
def export(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    L = lib(include_shared=bool(payload.get("include_shared")))
    req = ExamRequest.from_dict(payload)
    p = plan_exam(L, req)
    res = export_exam(L, p, record_usage=bool(payload.get("record_usage", True)))
    rel = res.folder.relative_to(L.exports_dir)
    return {"folder": str(res.folder), "course": rel.parts[0], "name": rel.parts[-1], "files": [{"name": f.name, "url": f"/api/exports/{rel.as_posix()}/{f.name}",
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
                info: dict[str, Any] = {}
                rec = d / "record.json"
                if rec.is_file():
                    try:
                        r = json.loads(rec.read_text(encoding="utf-8"))
                        rq = r.get("request") or {}
                        info = {"date": rq.get("date"), "professor": rq.get("professor"),
                                "n_versions": len(r.get("versions") or []) or None}
                    except (OSError, ValueError):
                        pass
                out.append({"course": d.parent.name, "name": d.name, "files": pdfs, **info,
                            "pairs": _pair_pdfs(pdfs, _sol_suffix(L)),
                            "folder": str(d), "modified": dt.datetime.fromtimestamp(d.stat().st_mtime).isoformat()})
    return out


def _pair_pdfs(names: list[str], suffix: str) -> list[dict[str, str | None]]:
    """[{exam, solution}] per version, using the configured solution suffix."""
    suffix = suffix or "_solution"
    sols = {n for n in names if Path(n).stem.endswith(suffix)}
    pairs: list[dict[str, str | None]] = []
    for n in names:
        if n in sols:
            continue
        sol = f"{Path(n).stem}{suffix}.pdf"
        pairs.append({"exam": n, "solution": sol if sol in sols else None})
    paired = {p["solution"] for p in pairs}
    pairs += [{"exam": None, "solution": n} for n in sorted(sols - paired)]
    return pairs


def _sol_suffix(L: Library) -> str:
    return (L.config.get("naming") or {}).get("solution_suffix") or "_solution"


def _export_folder(L: Library, course: str, folder: str) -> Path:
    base = L.exports_dir.resolve()
    d = (base / course / folder).resolve()
    if d.parent.parent != base or not d.is_dir():
        raise HTTPException(404, "Examen introuvable")
    return d


@app.get("/api/exports/{course}/{folder}.zip")
def zip_export(course: str, folder: str, which: str = Query("all", pattern="^(all|exams|solutions)$")):
    """All the PDFs of one generated exam in a ZIP (exams, solutions or both)."""
    L = lib()
    d = _export_folder(L, course, folder)
    suffix = _sol_suffix(L)
    pdfs = sorted(d.glob("*.pdf"))
    if which == "exams":
        pdfs = [f for f in pdfs if not f.stem.endswith(suffix)]
    elif which == "solutions":
        pdfs = [f for f in pdfs if f.stem.endswith(suffix)]
    if not pdfs:
        raise HTTPException(404, "Aucun PDF dans cet examen")
    import zipfile
    tmp = tempfile.NamedTemporaryFile(prefix="examgen-", suffix=".zip", delete=False)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in pdfs:
            z.write(f, f.name)
    tmp.close()
    label = {"all": "", "exams": "_examens", "solutions": "_solutions"}[which]
    from starlette.background import BackgroundTask
    return FileResponse(tmp.name, media_type="application/zip", filename=f"{course}_{folder}{label}.zip",
                        background=BackgroundTask(os.unlink, tmp.name))


@app.delete("/api/exports/{course}/{folder}")
def delete_export(course: str, folder: str) -> dict[str, bool]:
    """Delete one generated exam (its PDFs and LaTeX sources). Usage history is kept."""
    L = lib()
    d = _export_folder(L, course, folder)
    shutil.rmtree(d)
    if d.parent.is_dir() and not any(d.parent.iterdir()):
        d.parent.rmdir()
    return {"ok": True}


@app.get("/api/exports/{course}/{folder}/{name}")
def get_export(course: str, folder: str, name: str):
    L = lib()
    d = _export_folder(L, course, folder)
    p = (d / name).resolve()
    if p.parent != d or not p.is_file():
        raise HTTPException(404)
    # inline: the PDF opens in a browser tab; its real name is kept when the teacher saves it
    return FileResponse(p, media_type="application/pdf", filename=p.name, content_disposition_type="inline")


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
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "Adresse inconnue")
        f = _STATIC / full_path
        if full_path and f.is_file() and _STATIC in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(_STATIC / "index.html")

_ = exam_basename  # re-exported for clients
