"""The on-disk library: config, questions, exam definitions, exports."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .model import Question, QuestionError

FINAL = "final"


def exam_id(v: Any) -> int | str:
    """Normalise an exam identifier: 1, "2" -> int; "final" / "Final" -> FINAL."""
    if isinstance(v, bool):
        raise ValueError(f"Examen invalide : {v!r}")
    if isinstance(v, int):
        if v < 1:
            raise ValueError(f"Examen invalide : {v!r}")
        return v
    t = str(v).strip().lower()
    if t == FINAL:
        return FINAL
    if t.isdigit() and int(t) >= 1:
        return int(t)
    raise ValueError(f"Examen invalide : {v!r}")


def exam_sort_key(v: int | str) -> tuple[int, int]:
    return (1, 0) if v == FINAL else (0, int(v))


def exam_heading(number: int | str, title: str = "", label: str = "Examen") -> str:
    """Text of the exam heading on the cover: a custom title, "Examen final" or "Examen #2"."""
    if title:
        return title
    if number == FINAL:
        return f"{label} final"
    return rf"{label} \#{number}"

DEFAULT_COVER_INSTRUCTIONS = r"""\textbf{CONSIGNES POUR L'EXAMEN :} les éléments suivants sont exigés dans les solutions de problèmes :
\begin{itemize}[leftmargin=*, noitemsep]
    \item schéma de la situation avec identification des variables ;
    \item données initiales ;
    \item exposé clair de chaque étape de la solution avec titre ou courte phrase explicative, équations utilisées, résolution algébrique et calculs numériques (avec unités).
    \begin{itemize}
        \item Isolez algébriquement la variable recherchée avant de remplacer par les valeurs numériques.
        \item Faites le moins d'approximations possible lors de vos calculs.
        \item Donnez les réponses finales avec au moins trois chiffres significatifs.
    \end{itemize}
\end{itemize}
Les calculatrices programmables, téléphones cellulaires et autres appareils multimédias sont interdits.\\
Lorsque vous aurez terminé, brochez le questionnaire sur le dessus de votre examen."""

DEFAULT_COVER_NOTE = (r"Note importante : Si vous ne réussissez pas à trouver la réponse à une partie d'une question et "
                      r"vous avez besoin de cette réponse pour les parties suivantes, vous pouvez inventer une valeur "
                      r"pour poursuivre le problème et vous ne serez pas pénalisé.e tant que votre démarche reste "
                      r"cohérente à la valeur inventée!")

DEFAULT_CONFIG: dict[str, Any] = {
    "setup_done": False,
    "school": "",
    "logo": "",                 # image file in figures/, printed on the cover page
    "professors": [],
    "default_professor": "",
    # code -> {title, full_title, group, questions_from: [other course folders whose questions it may use]}
    "courses": {},
    "topics": {},               # optional pretty labels: {Onde_stationnaire: "Onde stationnaire / résonnante"}
    "latex": {"engine": "pdflatex", "path": ""},
    "time_margin": 0.2,
    "default_versions": 3,
    "naming": {
        # placeholders: {course} {exam} {session} {version} {date} {year}
        "file_pattern": "{course}_Examen_{exam}_{session}_v{version}",
        "solution_suffix": "_solution",
        "exam_label": "Examen",
        "version_label": "Version",
    },
    # session letter -> months (1-12). Québec default: Automne, Hiver, Été.
    "sessions": {"A": [8, 9, 10, 11, 12], "H": [1, 2, 3, 4, 5], "E": [6, 7]},
    "cover": {"instructions": DEFAULT_COVER_INSTRUCTIONS, "note": DEFAULT_COVER_NOTE,
              "professor_label": "Professeur", "name_label": "NOM"},
}


def merged_config(user: dict[str, Any]) -> dict[str, Any]:
    """Defaults + user values; nested dicts (naming, cover, latex) are merged key by key."""
    import copy
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    for k, v in (user or {}).items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict) and k in {"naming", "cover", "latex"}:
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    return cfg


def default_root() -> Path:
    env = os.environ.get("EXAM_APP_HOME")
    return Path(env).expanduser() if env else Path.home() / "exam_app"


@dataclass
class ExamSlot:
    topics: list[str]
    count: int = 1
    points: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"topics": self.topics} if len(self.topics) != 1 else {"topic": self.topics[0]}
        d["count"] = self.count
        if self.points is not None:
            d["points"] = self.points
        return d


@dataclass
class ExamSection:
    title: str
    type: str
    slots: list[ExamSlot] = field(default_factory=list)
    points: float | None = None  # section total (conceptual)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"title": self.title, "type": self.type}
        if self.points is not None:
            d["points"] = self.points
        d["slots"] = [s.to_dict() for s in self.slots]
        return d


@dataclass
class ExamDef:
    course: str
    number: int | str                # 1, 2, … or FINAL
    duration_min: int = 120
    sections: list[ExamSection] = field(default_factory=list)
    title: str = ""                  # optional custom name, e.g. "Examen de mi-session"

    @property
    def is_final(self) -> bool:
        return self.number == FINAL

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExamDef":
        secs = []
        for s in d.get("sections") or []:
            slots = []
            for sl in s.get("slots") or []:
                topics = sl.get("topics") or ([sl["topic"]] if sl.get("topic") else [])
                slots.append(ExamSlot(topics=[str(t) for t in topics], count=int(sl.get("count", 1)),
                                      points=sl.get("points")))
            secs.append(ExamSection(title=str(s.get("title", "")), type=str(s.get("type", "developpement")),
                                    slots=slots, points=s.get("points")))
        return cls(course=str(d["course"]), number=exam_id(d["number"]),
                   duration_min=int(d.get("duration_min", 120)), sections=secs,
                   title=str(d.get("title") or "").strip())

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"course": self.course, "number": self.number}
        if self.title:
            d["title"] = self.title
        d.update({"duration_min": self.duration_min, "sections": [s.to_dict() for s in self.sections]})
        return d


class Library:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root).expanduser() if root else default_root()
        self.questions_dir = self.root / "questions"
        self.figures_dir = self.root / "figures"
        self.templates_dir = self.root / "templates"
        self.exams_dir = self.root / "exams"
        self.exports_dir = self.root / "exports"
        self._cache: dict[str, Question] | None = None
        self._errors: dict[str, str] = {}
        self._stamp: tuple | None = None

    # ------------------------------------------------------------------ setup
    def ensure(self) -> "Library":
        for d in (self.questions_dir, self.figures_dir, self.templates_dir, self.exams_dir, self.exports_dir):
            d.mkdir(parents=True, exist_ok=True)
        if not (self.root / "config.yaml").exists():
            self.save_config(DEFAULT_CONFIG)
        return self

    @property
    def config(self) -> dict[str, Any]:
        p = self.root / "config.yaml"
        user = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
        cfg = merged_config(user or {})
        if user and "setup_done" not in user and user.get("school") and user.get("professors"):
            cfg["setup_done"] = True  # libraries created before the setup screen existed
        return cfg

    def save_config(self, cfg: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                                               encoding="utf-8")

    # -------------------------------------------------------------- questions
    def reload(self) -> None:
        self._cache = None

    def _fingerprint(self) -> tuple:
        """Cheap change detector for the question files (names, sizes, modification times)."""
        h, n = 0, 0
        if self.questions_dir.exists():
            for course in os.scandir(self.questions_dir):
                if not course.is_dir():
                    continue
                for topic in os.scandir(course.path):
                    if not topic.is_dir():
                        continue
                    for f in os.scandir(topic.path):
                        st = f.stat()
                        h ^= hash((f.name, st.st_mtime_ns, st.st_size, topic.name, course.name))
                        n += 1
        return (n, h)

    def refresh(self) -> None:
        """Re-read the questions only if a file changed on disk since the last load."""
        stamp = self._fingerprint()
        if stamp != self._stamp:
            self._cache = None
            self._stamp = stamp

    def _load_all(self) -> dict[str, Question]:
        if self._cache is not None:
            return self._cache
        qs: dict[str, Question] = {}
        errs: dict[str, str] = {}
        if self.questions_dir.exists():
            for y in sorted(self.questions_dir.glob("*/*/*.yaml")):
                try:
                    q = Question.load(y, self.questions_dir)
                    qs[q.id] = q
                except (QuestionError, yaml.YAMLError, OSError, ValueError) as exc:
                    errs[str(y.relative_to(self.questions_dir))] = str(exc)
        self._cache, self._errors = qs, errs
        return qs

    @property
    def load_errors(self) -> dict[str, str]:
        self._load_all()
        return self._errors

    def course_sources(self, course: str) -> list[str]:
        """Question folders a course draws from: its own, plus `questions_from` in config."""
        info = (self.config.get("courses") or {}).get(course) or {}
        extra = info.get("questions_from") or []
        if isinstance(extra, str):
            extra = [extra]
        return [course] + [c for c in extra if c != course]

    def questions(self, course: str | None = None, topic: str | None = None, qtype: str | None = None) -> list[Question]:
        out = []
        sources = set(self.course_sources(course)) if course else None
        for q in self._load_all().values():
            if sources is not None and q.course not in sources:
                continue
            if topic and q.topic != topic:
                continue
            if qtype and q.type != qtype:
                continue
            out.append(q)
        return out

    def get(self, qid: str) -> Question:
        try:
            return self._load_all()[qid]
        except KeyError as exc:
            raise KeyError(f"question introuvable : {qid}") from exc

    def save_question(self, q: Question) -> Path:
        p = q.save(self.questions_dir)
        self.reload()
        return p

    def delete_question(self, qid: str) -> None:
        q = self.get(qid)
        folder = self.questions_dir / q.course / q.topic
        for f in (f"{q.name}.yaml", f"{q.name}.tex", q.solution_file or f"{q.name}.sol.tex"):
            p = folder / f
            if p.exists():
                p.unlink()
        self.reload()

    def courses(self) -> list[str]:
        found = {p.name for p in self.questions_dir.iterdir() if p.is_dir()} if self.questions_dir.exists() else set()
        return sorted(found | set(self.config.get("courses", {})))

    def topics(self, course: str) -> list[str]:
        out: set[str] = set()
        for c in self.course_sources(course):
            d = self.questions_dir / c
            if d.exists():
                out |= {p.name for p in d.iterdir() if p.is_dir()}
        return sorted(out)

    # ------------------------------------------------------------------ exams
    def exam_path(self, course: str, number: int | str) -> Path:
        return self.exams_dir / course / f"examen_{exam_id(number)}.yaml"

    def exam_def(self, course: str, number: int | str) -> ExamDef:
        number = exam_id(number)
        p = self.exam_path(course, number)
        if p.exists():
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            return ExamDef.from_dict({**d, "course": course, "number": number})
        for src in self.course_sources(course)[1:]:  # borrow the structure of the bank it draws from
            sp = self.exam_path(src, number)
            if sp.exists():
                d = yaml.safe_load(sp.read_text(encoding="utf-8"))
                return ExamDef.from_dict({**d, "course": course, "number": number})
        topics = self.topics(course)
        dev = [t for t in topics if self.questions(course, t, "developpement")]
        con = [t for t in topics if self.questions(course, t, "conceptuel")]
        if number == FINAL:
            # the final exam covers the whole course: every topic is eligible, spread over up to five
            # development questions (80 points) plus conceptual questions (20 points), longer sitting
            n = min(len(dev), 5)
            secs = [ExamSection("Questions à développement", "developpement",
                                [ExamSlot(dev[i::n], 1, 80 // n) for i in range(n)])]
            if con:
                secs.append(ExamSection("Questions conceptuelles", "conceptuel", [ExamSlot(con, 8)], points=20))
            return ExamDef(course, number, 180, secs)
        # default: one development question per topic, 20 points each
        secs = [ExamSection("Questions à développement", "developpement",
                            [ExamSlot([t], 1, 20) for t in dev[:4]])]
        if con:
            secs.append(ExamSection("Questions conceptuelles", "conceptuel", [ExamSlot(con, 5)], points=20))
        return ExamDef(course, number, 120, secs)

    def exam_numbers(self, course: str) -> list[int | str]:
        """Exams with a saved structure for this course: 1, 2, … then "final"."""
        d = self.exams_dir / course
        nums: list[int | str] = []
        if d.exists():
            for p in d.glob("examen_*.yaml"):
                try:
                    nums.append(exam_id(p.stem.split("_", 1)[1]))
                except (IndexError, ValueError):
                    pass
        return sorted(set(nums), key=exam_sort_key)

    def delete_exam_def(self, course: str, number: int | str) -> bool:
        p = self.exam_path(course, number)
        if p.exists():
            p.unlink()
            return True
        return False

    def save_exam_def(self, e: ExamDef) -> Path:
        p = self.exam_path(e.course, e.number)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(e.to_dict(), allow_unicode=True, sort_keys=False), encoding="utf-8")
        return p

    # ----------------------------------------------------------------- assets
    def template(self, name: str, course: str | None = None) -> str:
        """User template (per course, then global) falling back to the built-in one."""
        candidates = []
        if course:
            candidates.append(self.templates_dir / course / name)
        candidates.append(self.templates_dir / name)
        for c in candidates:
            if c.exists():
                return c.read_text(encoding="utf-8")
        return (Path(__file__).parent / "templates" / name).read_text(encoding="utf-8")

    def copy_figures(self, names: list[str], dest: Path) -> list[str]:
        missing = []
        fig_dest = dest / "Figures"
        fig_dest.mkdir(parents=True, exist_ok=True)
        for n in names:
            src = self.figures_dir / Path(n).name
            if src.exists():
                shutil.copy2(src, fig_dest / src.name)
            else:
                missing.append(n)
        return missing
