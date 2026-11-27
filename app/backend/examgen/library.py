"""The on-disk library: config, questions, exam definitions, exports."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .model import Question, QuestionError

DEFAULT_CONFIG: dict[str, Any] = {
    "school": "Cégep de Valleyfield",
    "professors": ["Jonathan Meloche-Gagnon"],
    "default_professor": "Jonathan Meloche-Gagnon",
    "courses": {
        "203-SN3-RE": {"title": "Physique", "full_title": "Ondes et physique moderne", "group": "groupe 2"},
    },
    "topics": {},  # optional pretty labels: {Onde_stationnaire: "Onde stationnaire / résonnante"}
    "latex": {"engine": "pdflatex", "path": ""},
    "time_margin": 0.2,
    "default_versions": 3,
}


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
    number: int
    duration_min: int = 120
    sections: list[ExamSection] = field(default_factory=list)

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
        return cls(course=str(d["course"]), number=int(d["number"]),
                   duration_min=int(d.get("duration_min", 120)), sections=secs)

    def to_dict(self) -> dict[str, Any]:
        return {"course": self.course, "number": self.number, "duration_min": self.duration_min,
                "sections": [s.to_dict() for s in self.sections]}


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
        cfg = dict(DEFAULT_CONFIG)
        if p.exists():
            cfg.update(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
        return cfg

    def save_config(self, cfg: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                                               encoding="utf-8")

    # -------------------------------------------------------------- questions
    def reload(self) -> None:
        self._cache = None

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

    def questions(self, course: str | None = None, topic: str | None = None, qtype: str | None = None) -> list[Question]:
        out = []
        for q in self._load_all().values():
            if course and q.course != course:
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
        d = self.questions_dir / course
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.exists() else []

    # ------------------------------------------------------------------ exams
    def exam_path(self, course: str, number: int) -> Path:
        return self.exams_dir / course / f"examen_{number}.yaml"

    def exam_def(self, course: str, number: int) -> ExamDef:
        p = self.exam_path(course, number)
        if p.exists():
            return ExamDef.from_dict(yaml.safe_load(p.read_text(encoding="utf-8")))
        # default: one development question per topic, 20 points each
        topics = self.topics(course)
        dev = [t for t in topics if self.questions(course, t, "developpement")]
        con = [t for t in topics if self.questions(course, t, "conceptuel")]
        secs = [ExamSection("Questions à développement", "developpement",
                            [ExamSlot([t], 1, 20) for t in dev[:4]])]
        if con:
            secs.append(ExamSection("Questions conceptuelles", "conceptuel", [ExamSlot(con, 5)], points=20))
        return ExamDef(course, number, 120, secs)

    def exam_numbers(self, course: str) -> list[int]:
        d = self.exams_dir / course
        nums = []
        if d.exists():
            for p in d.glob("examen_*.yaml"):
                try:
                    nums.append(int(p.stem.split("_")[1]))
                except (IndexError, ValueError):
                    pass
        return sorted(nums)

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
