"""Exam generation: pick questions, draw values per version, build and compile PDFs."""
from __future__ import annotations

import datetime as dt
import re
import json
import random
import shutil
import statistics
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import latex, values as V
from .library import ExamDef, ExamSection, Library
from .model import Question
from .solve import SolveError, solve_parts, auto_solution_tex

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
             "octobre", "novembre", "décembre"]


# ------------------------------------------------------------------ naming helpers
DEFAULT_SESSIONS = {"A": [8, 9, 10, 11, 12], "H": [1, 2, 3, 4, 5], "E": [6, 7]}
DEFAULT_PATTERN = "{course}_Examen_{exam}_{session}_v{version}"


def session_code(d: dt.date, sessions: dict[str, list[int]] | None = None) -> str:
    """Session letter from the month (Québec default: Aug-Dec A, Jan-May H, Jun-Jul E) + 2-digit year."""
    letter = next((k for k, months in (sessions or DEFAULT_SESSIONS).items() if d.month in months), "")
    return f"{letter}{d.year % 100:02d}"


def date_long_fr(d: dt.date) -> str:
    day = "1er" if d.day == 1 else str(d.day)
    return f"{day} {MONTHS_FR[d.month - 1]} {d.year}"


def duration_text(minutes: int) -> str:
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h} h {m:02d}"
    if h:
        return f"{h} h"
    return f"{m} min"


def exam_basename(course: str, number: int, d: dt.date, version: int, cfg: dict | None = None) -> str:
    cfg = cfg or {}
    pattern = (cfg.get("naming") or {}).get("file_pattern") or DEFAULT_PATTERN
    name = pattern.format_map(_SafeDict(course=course, exam=number, session=session_code(d, cfg.get("sessions")),
                                        version=version, date=d.isoformat(), year=d.year))
    return re.sub(r'[<>:"/\\|?*]+', "-", name).strip()


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def solution_suffix(cfg: dict | None) -> str:
    return ((cfg or {}).get("naming") or {}).get("solution_suffix", "_solution")


# ------------------------------------------------------------------ data classes
@dataclass
class ExamRequest:
    course: str
    exam_number: int
    date: dt.date
    professor: str
    duration_min: int = 120
    n_versions: int = 3
    mode: str = "same"            # same | different
    seed: int | None = None
    shuffle_conceptual: bool = True
    shuffle_choices: bool = True
    group: str | None = None
    exam_def: ExamDef | None = None
    locks: dict[str, str] = field(default_factory=dict)       # slot key -> question id
    swaps: dict[str, str] = field(default_factory=dict)       # same as locks, applied once
    time_margin: float | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExamRequest":
        d = dict(d)
        date = d.get("date")
        if isinstance(date, str):
            date = dt.date.fromisoformat(date[:10])
        ed = d.get("exam_def")
        return cls(
            course=d["course"], exam_number=int(d["exam_number"]), date=date or dt.date.today(),
            professor=d.get("professor", ""), duration_min=int(d.get("duration_min", 120)),
            n_versions=int(d.get("n_versions", 3)), mode=d.get("mode", "same"), seed=d.get("seed"),
            shuffle_conceptual=bool(d.get("shuffle_conceptual", True)),
            shuffle_choices=bool(d.get("shuffle_choices", True)), group=d.get("group"),
            exam_def=ExamDef.from_dict(ed) if isinstance(ed, dict) else ed,
            locks=dict(d.get("locks") or {}), swaps=dict(d.get("swaps") or {}),
            time_margin=d.get("time_margin"),
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        d["exam_def"] = self.exam_def.to_dict() if self.exam_def else None
        return d


@dataclass
class Slot:
    key: str
    section: int
    topics: list[str]
    type: str
    points: float | None


@dataclass
class Placed:
    slot: str
    section: int
    question_id: str
    points: float
    values: dict[str, Any] = field(default_factory=dict)
    choice_order: list[int] = field(default_factory=list)   # permutation of original choices
    answer: str = ""                                        # letter after shuffling


@dataclass
class VersionPlan:
    number: int
    placed: list[Placed]


@dataclass
class ExamPlan:
    request: ExamRequest
    exam_def: ExamDef
    seed: int
    versions: list[VersionPlan]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self, lib: Library | None = None) -> dict[str, Any]:
        out = {"request": self.request.to_dict(), "exam_def": self.exam_def.to_dict(), "seed": self.seed,
               "warnings": self.warnings, "versions": []}
        for v in self.versions:
            items = []
            for p in v.placed:
                item = asdict(p)
                if lib is not None:
                    try:
                        q = lib.get(p.question_id)
                        item.update(title=q.title, time_min=q.time_min, difficulty=q.difficulty, type=q.type,
                                    topic=q.topic)
                    except KeyError:
                        pass
                items.append(item)
            out["versions"].append({"number": v.number, "placed": items,
                                    "basename": exam_basename(self.request.course, self.request.exam_number,
                                                              self.request.date, v.number,
                                                              lib.config if lib is not None else None)})
        return out


# ------------------------------------------------------------------ selection
def expand_slots(ed: ExamDef) -> list[Slot]:
    slots = []
    for si, sec in enumerate(ed.sections):
        total_count = sum(s.count for s in sec.slots) or 1
        for li, sl in enumerate(sec.slots):
            pts = sl.points
            if pts is None and sec.points is not None:
                pts = float(sec.points) / total_count
            for k in range(sl.count):
                slots.append(Slot(f"{si}.{li}.{k}", si, sl.topics, sec.type, pts))
    return slots


def _usage_count(usage: dict[str, list[dict]], qid: str) -> int:
    return len(usage.get(qid, []))


def _score(chosen: list[Question], target_time: float, usage: dict[str, list[dict]]) -> float:
    if not chosen:
        return 1e9
    total = sum(q.time_min for q in chosen)
    over = max(0.0, total - target_time) / max(target_time, 1)
    under = max(0.0, 0.7 * target_time - total) / max(target_time, 1)
    diffs = [q.difficulty for q in chosen]
    balance = abs(statistics.mean(diffs) - 3) * 0.1
    recency = sum(_usage_count(usage, q.id) for q in chosen) * 0.05
    return 3 * over + under + balance + recency


def pick_questions(lib: Library, slots: list[Slot], course: str, rng: random.Random, target_time: float,
                   locks: dict[str, str], exclude: set[str], usage: dict[str, list[dict]],
                   trials: int = 300) -> tuple[dict[str, Question], list[str]]:
    pools: dict[str, list[Question]] = {}
    warnings: list[str] = []
    for s in slots:
        pool = [q for t in s.topics for q in lib.questions(course, t, s.type)]
        pools[s.key] = pool
        if not pool and s.key not in locks:
            warnings.append(f"Aucune question {s.type} pour {', '.join(s.topics)}")
    best: dict[str, Question] = {}
    best_score = float("inf")
    for _ in range(trials):
        chosen: dict[str, Question] = {}
        used: set[str] = set()
        for s in slots:
            if s.key in locks:
                try:
                    q = lib.get(locks[s.key])
                    chosen[s.key] = q
                    used.add(q.id)
                except KeyError:
                    warnings.append(f"Question verrouillée introuvable : {locks[s.key]}")
                continue
            pool = pools[s.key]
            cand = [q for q in pool if q.id not in used and q.id not in exclude]
            if not cand:
                cand = [q for q in pool if q.id not in used]
            if not cand:
                continue
            weights = [1.0 / (1 + _usage_count(usage, q.id)) for q in cand]
            q = rng.choices(cand, weights=weights, k=1)[0]
            chosen[s.key] = q
            used.add(q.id)
        sc = _score(list(chosen.values()), target_time, usage)
        if sc < best_score:
            best, best_score = chosen, sc
        if not any(s.key not in locks for s in slots):
            break
    filled = {s.key for s in slots} - set(best)
    for k in sorted(filled):
        warnings.append(f"Case {k} vide (pas assez de questions)")
    return best, sorted(set(warnings))


def _choice_shuffle(q: Question, rng: random.Random, shuffle: bool) -> tuple[list[int], str]:
    if not q.choices:
        return [], q.answer
    order = list(range(len(q.choices)))
    if shuffle:
        n_fixed = max(0, min(q.pin_last, len(order)))
        head = order[:len(order) - n_fixed]
        rng.shuffle(head)
        order = head + order[len(order) - n_fixed:]
    answer = q.answer
    if q.answer:
        orig = ord(q.answer.upper()) - 65
        if 0 <= orig < len(order):
            answer = chr(65 + order.index(orig))
    return order, answer


def plan_exam(lib: Library, req: ExamRequest) -> ExamPlan:
    ed = req.exam_def or lib.exam_def(req.course, req.exam_number)
    ed.duration_min = req.duration_min
    seed = req.seed if req.seed is not None else random.randrange(1, 2**31)
    rng = random.Random(seed)
    margin = req.time_margin if req.time_margin is not None else float(lib.config.get("time_margin", 0.2))
    target = req.duration_min * (1 - margin)
    slots = expand_slots(ed)
    usage = load_usage(lib)
    all_locks = {**req.locks, **req.swaps}
    locks = {k: v for k, v in all_locks.items() if ":" not in k}
    warnings: list[str] = []

    def version_locks(n: int) -> dict[str, str]:
        out = dict(locks)
        for k, v in all_locks.items():
            if ":" in k:
                vn, slot = k.split(":", 1)
                if vn == str(n):
                    out[slot] = v
        return out

    picks_per_version: list[dict[str, Question]] = []
    if req.mode == "different":
        seen: set[str] = set()
        for n in range(1, req.n_versions + 1):
            chosen, w = pick_questions(lib, slots, req.course, rng, target, version_locks(n), seen, usage)
            warnings += w
            seen |= {q.id for q in chosen.values()}
            picks_per_version.append(chosen)
    else:
        chosen, w = pick_questions(lib, slots, req.course, rng, target, version_locks(1), set(), usage)
        warnings += w
        picks_per_version = [chosen] * req.n_versions

    history: dict[str, list[dict[str, Any]]] = {}
    versions: list[VersionPlan] = []
    for vi, chosen in enumerate(picks_per_version, start=1):
        placed: list[Placed] = []
        for s in slots:
            q = chosen.get(s.key)
            if q is None:
                continue
            try:
                vals = V.draw(q, rng, avoid=history.get(q.id, []))
            except V.DrawError as exc:
                warnings.append(str(exc))
                vals = {n: V.draw_variable(v, rng) for n, v in q.variables.items()}
            history.setdefault(q.id, []).append(vals)
            order, answer = _choice_shuffle(q, rng, req.shuffle_choices)
            pts = s.points if s.points is not None else q.points
            placed.append(Placed(s.key, s.section, q.id, float(pts), vals, order, answer))
        if req.shuffle_conceptual:
            for si, sec in enumerate(ed.sections):
                if sec.type != "conceptuel":
                    continue
                idx = [i for i, p in enumerate(placed) if p.section == si]
                items = [placed[i] for i in idx]
                rng.shuffle(items)
                for i, p in zip(idx, items):
                    placed[i] = p
        versions.append(VersionPlan(vi, placed))
    return ExamPlan(req, ed, seed, versions, sorted(set(warnings)))


def alternatives(lib: Library, ed: ExamDef, course: str, slot_key: str, exclude: set[str]) -> list[Question]:
    slot = next((s for s in expand_slots(ed) if s.key == slot_key), None)
    if slot is None:
        return []
    return [q for t in slot.topics for q in lib.questions(course, t, slot.type) if q.id not in exclude]


# ------------------------------------------------------------------ rendering
def question_tex(q: Question, p: Placed) -> str:
    disp = V.formatted(q, p.values)
    si = V.formatted_si(q, p.values)
    body = q.clean_body
    if q.choices:
        body = body.replace("\\choices", latex.render_choices([q.choices[i] for i in (p.choice_order or range(len(q.choices)))]))
    return latex.substitute(body, disp, si)


def solution_tex(q: Question, p: Placed) -> str:
    disp = V.formatted(q, p.values)
    si = V.formatted_si(q, p.values)
    parts: list[str] = []
    if q.type == "conceptuel":
        if p.answer:
            parts.append(rf"\textbf{{Réponse : {p.answer}}}")
        if q.explanation:
            parts.append(latex.substitute(q.explanation, disp, si))
    if q.solution_mode == "manual":
        parts.append(latex.substitute(q.solution_tex, disp, si))
    elif q.solution_mode == "auto":
        try:
            parts.append(auto_solution_tex(q, p.values))
        except (SolveError, Exception) as exc:  # noqa: BLE001 - shown in the PDF, never fatal
            parts.append(rf"\textit{{Solution automatique impossible : {latex_escape(str(exc))}}}")
    elif q.solution_mode == "answers_only":
        try:
            parts.extend(r.latex for r in solve_parts(q, p.values))
        except (SolveError, Exception) as exc:  # noqa: BLE001
            parts.append(rf"\textit{{Calcul impossible : {latex_escape(str(exc))}}}")
    elif q.type != "conceptuel":
        parts.append(r"\textit{Aucune solution fournie pour cette question.}")
    return "\n\n".join(x for x in parts if x)


def latex_escape(s: str) -> str:
    for a, b in (("\\", r"\textbackslash{}"), ("_", r"\_"), ("&", r"\&"), ("%", r"\%"), ("#", r"\#"),
                 ("$", r"\$"), ("{", r"\{"), ("}", r"\}"), ("^", r"\^{}"), ("~", r"\~{}")):
        s = s.replace(a, b)
    return s


def _fmt_points(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else V.fmt_plain(round(x, 2))


def _summary_text(ed: ExamDef, placed: list[Placed], lib: Library) -> str:
    n_dev = sum(1 for p in placed if ed.sections[p.section].type == "developpement")
    n_con = sum(1 for p in placed if ed.sections[p.section].type == "conceptuel")
    bits = []
    if n_dev:
        bits.append(f"{n_dev} question{'s' if n_dev > 1 else ''} à développement")
    if n_con:
        bits.append(f"{n_con} question{'s' if n_con > 1 else ''} conceptuelle{'s' if n_con > 1 else ''}")
    return " et ".join(bits) or "0 question"


def logo_tex(lib: Library) -> str:
    logo = (lib.config.get("logo") or "").strip()
    if logo and (lib.figures_dir / Path(logo).name).exists():
        return rf"\includegraphics[height=1.3cm]{{Figures/{Path(logo).name}}}\par\smallskip{{}}"
    return ""


def build_document(lib: Library, plan: ExamPlan, vp: VersionPlan, *, with_solutions: bool) -> tuple[str, list[str]]:
    req, ed = plan.request, plan.exam_def
    cfg = lib.config
    course_cfg = (cfg.get("courses") or {}).get(req.course, {})
    group = req.group if req.group is not None else course_cfg.get("group", "")
    total = sum(p.points for p in vp.placed)
    naming = cfg.get("naming") or {}
    cover = cfg.get("cover") or {}
    fields = {
        "version": str(vp.number),
        "school": cfg.get("school", ""),
        "course": req.course,
        "course_title": course_cfg.get("title", ""),
        "group_paren": f" ({group})" if group else "",
        "date_long": date_long_fr(req.date),
        "professor": req.professor,
        "duration": duration_text(req.duration_min),
        "exam_number": str(req.exam_number),
        "total": _fmt_points(total),
        "summary": _summary_text(ed, vp.placed, lib),
        "solution_banner": r"\\[0.3cm]\Large\textbf{SOLUTIONNAIRE}" if with_solutions else "",
        "exam_label": naming.get("exam_label", "Examen"),
        "version_label": naming.get("version_label", "Version"),
        "professor_label": cover.get("professor_label", "Professeur"),
        "name_label": cover.get("name_label", "NOM"),
        "instructions": cover.get("instructions", ""),
        "note": cover.get("note", ""),
        "logo": logo_tex(lib),
    }
    out = [latex.fill(lib.template("preamble.tex", req.course), fields), r"\begin{document}",
           latex.fill(lib.template("cover.tex", req.course), fields)]
    figures: list[str] = []
    for si, sec in enumerate(ed.sections):
        items = [p for p in vp.placed if p.section == si]
        if not items:
            continue
        sec_pts = sum(p.points for p in items)
        if sec.type == "conceptuel":
            out.append(rf"\section{{{sec.title} (\rule{{1cm}}{{0.4pt}}/{_fmt_points(sec_pts)} points)}}")
        else:
            out.append(rf"\section{{{sec.title}}}")
        for p in items:
            q = lib.get(p.question_id)
            figures += q.figures
            out.append(f"{latex.MARKER}{q.id}")
            if sec.type == "conceptuel":
                out.append(r"\subsection{}")
            else:
                out.append(rf"\subsection{{(\rule{{1cm}}{{0.4pt}}/{_fmt_points(p.points)} points)}}")
            out.append(question_tex(q, p))
            if with_solutions:
                out.append(r"\par\medskip\noindent\rule{\linewidth}{0.8pt}\par\textbf{\large Solution}\par")
                out.append(solution_tex(q, p))
            if sec.type != "conceptuel":
                out.append(r"\newpage")
        out.append(f"{latex.MARKER}")
    out.append(rf"\hfill \textbf{{Total : {_fmt_points(total)} points}}")
    out.append(r"\end{document}")
    return "\n\n".join(out) + "\n", sorted(set(figures))


# ------------------------------------------------------------------ export
@dataclass
class ExportResult:
    folder: Path
    files: list[Path]
    record: Path
    warnings: list[str]


def export_dir(lib: Library, req: ExamRequest) -> Path:
    return lib.exports_dir / req.course / f"Examen_{req.exam_number}_{session_code(req.date, lib.config.get('sessions'))}"


def export_exam(lib: Library, plan: ExamPlan, *, record_usage: bool = True, keep_tex: bool = True) -> ExportResult:
    req = plan.request
    folder = export_dir(lib, req)
    folder.mkdir(parents=True, exist_ok=True)
    cfg = lib.config.get("latex") or {}
    files: list[Path] = []
    warnings = list(plan.warnings)
    with tempfile.TemporaryDirectory(prefix="examgen-") as tmp:
        tmpd = Path(tmp)
        for vp in plan.versions:
            base = exam_basename(req.course, req.exam_number, req.date, vp.number, lib.config)
            for with_sol, suffix in ((False, ""), (True, solution_suffix(lib.config))):
                tex, figs = build_document(lib, plan, vp, with_solutions=with_sol)
                if lib.config.get("logo"):
                    figs = figs + [Path(lib.config["logo"]).name]
                missing = lib.copy_figures(figs, tmpd)
                warnings += [f"Figure introuvable : {m}" for m in missing]
                res = latex.compile_tex(tex, tmpd, base + suffix, engine=cfg.get("engine", "pdflatex"),
                                        engine_path=cfg.get("path", ""))
                dest = folder / f"{base}{suffix}.pdf"
                shutil.copy2(res.pdf, dest)
                files.append(dest)
                if keep_tex:
                    (folder / "tex").mkdir(exist_ok=True)
                    (folder / "tex" / f"{base}{suffix}.tex").write_text(tex, encoding="utf-8")
    record = folder / "record.json"
    data = plan.to_dict(lib)
    data["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    data["files"] = [f.name for f in files]
    # answers for the record (best effort)
    for v in data["versions"]:
        for item in v["placed"]:
            q = lib.get(item["question_id"])
            if q.parts:
                try:
                    item["answers"] = {r.key: {"name": r.name, "value": r.value, "unit": r.unit}
                                       for r in solve_parts(q, item["values"], with_latex=False)}
                except Exception as exc:  # noqa: BLE001
                    item["answers_error"] = str(exc)
    record.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if record_usage:
        add_usage(lib, plan)
    return ExportResult(folder, files, record, sorted(set(warnings)))


# ------------------------------------------------------------------ usage history
def _usage_path(lib: Library) -> Path:
    return lib.root / "usage.json"


def load_usage(lib: Library) -> dict[str, list[dict]]:
    p = _usage_path(lib)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def add_usage(lib: Library, plan: ExamPlan) -> None:
    usage = load_usage(lib)
    req = plan.request
    tag = f"Examen_{req.exam_number}_{session_code(req.date, lib.config.get('sessions'))}"
    for vp in plan.versions:
        for p in vp.placed:
            entries = usage.setdefault(p.question_id, [])
            entry = {"date": req.date.isoformat(), "exam": tag, "course": req.course}
            if entry not in entries:
                entries.append(entry)
    _usage_path(lib).write_text(json.dumps(usage, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ single question preview / test
def preview_question(lib: Library, q: Question, *, seed: int = 1, n: int = 1, with_solution: bool = True,
                     workdir: Path | None = None) -> tuple[Path, list[dict[str, Any]]]:
    """Compile one question with `n` random value sets. Returns the PDF and the drawn values."""
    rng = random.Random(seed)
    draws: list[dict[str, Any]] = []
    sec_type = q.type
    ed = ExamDef(q.course, 0, 0, [ExamSection("Aperçu", sec_type, [])])
    req = ExamRequest(q.course, 0, dt.date.today(), "", n_versions=n)
    cfg = lib.config.get("latex") or {}
    chunks = [latex.fill(lib.template("preamble.tex", q.course), {"version": "1"}), r"\begin{document}"]
    for i in range(n):
        vals = V.draw(q, rng, avoid=draws)
        draws.append(vals)
        order, answer = _choice_shuffle(q, rng, False)
        p = Placed("0.0.0", 0, q.id, q.points, vals, order, answer)
        chunks.append(f"{latex.MARKER}{q.id}")
        label = ", ".join(f"{k} = {V.fmt_plain(v) if not isinstance(v, str) else '(texte)'}" for k, v in vals.items())
        chunks.append(rf"\section*{{Tirage {i + 1}}}\textit{{\small {latex_escape(label)}}}")
        chunks.append(r"\subsection*{}" if q.type == "conceptuel" else rf"\subsection*{{({_fmt_points(q.points)} points)}}")
        chunks.append(question_tex(q, p))
        if with_solution:
            chunks.append(r"\par\medskip\noindent\rule{\linewidth}{0.8pt}\par\textbf{\large Solution}\par")
            chunks.append(solution_tex(q, p))
        chunks.append(r"\newpage")
    chunks.append(r"\end{document}")
    tex = "\n\n".join(chunks)
    own_tmp = workdir is None
    wd = Path(tempfile.mkdtemp(prefix="examgen-q-")) if own_tmp else workdir
    lib.copy_figures(q.figures, wd)
    res = latex.compile_tex(tex, wd, "apercu", engine=cfg.get("engine", "pdflatex"),
                            engine_path=cfg.get("path", ""), runs=1)
    _ = (ed, req)
    return res.pdf, draws
