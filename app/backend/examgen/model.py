"""Question model: loading and validating <name>.yaml + <name>.tex (+ <name>.sol.tex)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import expr

VAR_TYPES = {"integer", "decimal", "sigfig", "choice", "text"}
QUESTION_TYPES = {"developpement", "conceptuel"}
SOLUTION_MODES = {"manual", "auto", "answers_only", "none"}
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
VAR_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
VREF_RE = re.compile(r"\\(v|vsi)\{([^{}]*)\}")
LEADING_SUBSECTION_RE = re.compile(r"^\s*\\subsection\*?\{\}\s*")


class QuestionError(ValueError):
    pass


@dataclass
class Variable:
    name: str
    type: str
    min: float | None = None
    max: float | None = None
    step: float | None = None
    decimals: int | None = None
    sigfigs: int = 3
    values: list[Any] = field(default_factory=list)
    unit: str = ""
    label: str = ""
    si: float = 1.0
    si_unit: str = ""
    symbol: str = ""

    @classmethod
    def from_dict(cls, name: str, d: dict[str, Any]) -> "Variable":
        if not VAR_NAME_RE.match(name):
            raise QuestionError(f"nom de variable invalide : {name!r}")
        d = dict(d or {})
        vtype = d.get("type", "decimal")
        if vtype not in VAR_TYPES:
            raise QuestionError(f"{name}: type inconnu {vtype!r}")
        si = d.get("si", 1.0)
        si_unit = d.get("si_unit", "")
        if isinstance(si, str):
            parts = si.split()
            try:
                si_f = float(parts[0])
            except (ValueError, IndexError) as exc:
                raise QuestionError(f"{name}: si invalide {si!r}") from exc
            if len(parts) > 1 and not si_unit:
                si_unit = " ".join(parts[1:])
            si = si_f
        v = cls(
            name=name,
            type=vtype,
            min=_num(d.get("min")),
            max=_num(d.get("max")),
            step=_num(d.get("step")),
            decimals=d.get("decimals"),
            sigfigs=int(d.get("sigfigs", 3)),
            values=list(d.get("values") or []),
            unit=str(d.get("unit", "") or ""),
            label=str(d.get("label", "") or ""),
            si=float(si),
            si_unit=str(si_unit or ""),
            symbol=str(d.get("symbol", "") or ""),
        )
        v.validate()
        return v

    def validate(self) -> None:
        if self.type in {"choice", "text"}:
            if not self.values:
                raise QuestionError(f"{self.name}: 'values' est requis pour le type {self.type}")
            if self.type == "choice":
                try:
                    self.values = [float(x) if not isinstance(x, int) else x for x in self.values]
                except (TypeError, ValueError) as exc:
                    raise QuestionError(f"{self.name}: 'values' doit contenir des nombres") from exc
            return
        if self.min is None or self.max is None:
            raise QuestionError(f"{self.name}: 'min' et 'max' sont requis")
        if self.min > self.max:
            raise QuestionError(f"{self.name}: min > max")
        if self.step is not None and self.step <= 0:
            raise QuestionError(f"{self.name}: step doit être positif")

    @property
    def numeric(self) -> bool:
        return self.type != "text"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type}
        if self.type in {"choice", "text"}:
            d["values"] = self.values
        else:
            conv = (lambda x: int(x)) if self.type == "integer" else _intify
            d["min"] = conv(self.min)
            d["max"] = conv(self.max)
            if self.step is not None:
                d["step"] = conv(self.step)
            if self.decimals is not None:
                d["decimals"] = self.decimals
            if self.type == "sigfig":
                d["sigfigs"] = self.sigfigs
        for key in ("unit", "label", "si_unit", "symbol"):
            if getattr(self, key):
                d[key] = getattr(self, key)
        if self.si != 1.0:
            d["si"] = self.si
        return d


def _num(x: Any) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError) as exc:
        raise QuestionError(f"nombre invalide : {x!r}") from exc


@dataclass
class Part:
    key: str
    find: str = ""
    equation: str = ""
    expr: str = ""
    unit: str = ""
    label: str = ""
    symbol: str = ""
    root: str = "positive"
    sigfigs: int = 3

    @classmethod
    def from_dict(cls, key: str, d: dict[str, Any]) -> "Part":
        d = dict(d or {})
        return cls(
            key=str(key),
            find=str(d.get("find", "") or ""),
            equation=str(d.get("equation", "") or ""),
            expr=str(d.get("expr", "") or ""),
            unit=str(d.get("unit", "") or ""),
            label=str(d.get("label", "") or ""),
            symbol=str(d.get("symbol", "") or ""),
            root=str(d.get("root", "positive")),
            sigfigs=int(d.get("sigfigs", 3)),
        )

    def to_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in ("find", "equation", "expr", "unit", "label", "symbol") if getattr(self, k)}
        if self.root != "positive":
            d["root"] = self.root
        if self.sigfigs != 3:
            d["sigfigs"] = self.sigfigs
        return d


@dataclass
class Question:
    id: str                       # <course>/<topic>/<name>
    course: str
    topic: str
    name: str
    title: str
    type: str
    points: float
    time_min: float
    difficulty: int
    body: str
    variables: dict[str, Variable] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    solution_mode: str = "none"
    solution_tex: str = ""
    solution_file: str = ""
    parts: list[Part] = field(default_factory=list)
    figures: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    answer: str = ""
    explanation: str = ""
    choices: list[str] = field(default_factory=list)
    pin_last: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, yaml_path: Path, questions_root: Path) -> "Question":
        yaml_path = Path(yaml_path)
        rel = yaml_path.relative_to(questions_root)
        if len(rel.parts) != 3:
            raise QuestionError(f"{rel}: chemin attendu <cours>/<thème>/<nom>.yaml")
        course, topic, fname = rel.parts
        name = fname[: -len(".yaml")]
        meta = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        tex_path = yaml_path.with_suffix(".tex")
        if not tex_path.exists():
            raise QuestionError(f"{rel}: fichier {tex_path.name} manquant")
        body = tex_path.read_text(encoding="utf-8")
        q = cls.from_dict(f"{course}/{topic}/{name}", meta, body, base_dir=yaml_path.parent)
        q.path = yaml_path
        return q

    @classmethod
    def from_dict(cls, qid: str, meta: dict[str, Any], body: str, *, solution_tex: str | None = None,
                  base_dir: Path | None = None) -> "Question":
        course, topic, name = qid.split("/")
        meta = dict(meta or {})
        known = {"title", "type", "points", "time_min", "difficulty", "variables", "constraints", "solution",
                 "figures", "tags", "answer", "explanation", "choices", "pin_last", "history"}
        sol = dict(meta.get("solution") or {})
        mode = sol.get("mode", "none")
        if mode not in SOLUTION_MODES:
            raise QuestionError(f"{qid}: solution.mode inconnu {mode!r}")
        sol_file = sol.get("file", f"{name}.sol.tex" if mode == "manual" else "")
        if solution_tex is None:
            solution_tex = ""
            if mode == "manual" and base_dir is not None:
                p = base_dir / sol_file
                if p.exists():
                    solution_tex = p.read_text(encoding="utf-8")
        parts_raw = sol.get("parts") or {}
        if isinstance(parts_raw, list):  # allow list form [{key: a, ...}]
            parts = [Part.from_dict(p.get("key", chr(97 + i)), p) for i, p in enumerate(parts_raw)]
        else:
            parts = [Part.from_dict(k, v) for k, v in parts_raw.items()]
        variables = {k: Variable.from_dict(k, v) for k, v in (meta.get("variables") or {}).items()}
        q = cls(
            id=qid, course=course, topic=topic, name=name,
            title=str(meta.get("title") or name),
            type=str(meta.get("type", "developpement")),
            points=float(meta.get("points", 0) or 0),
            time_min=float(meta.get("time_min", 0) or 0),
            difficulty=int(meta.get("difficulty", 3) or 3),
            body=body,
            variables=variables,
            constraints=[str(c) for c in (meta.get("constraints") or [])],
            solution_mode=mode,
            solution_tex=solution_tex,
            solution_file=sol_file,
            parts=parts,
            figures=[str(f) for f in (meta.get("figures") or [])],
            tags=[str(t) for t in (meta.get("tags") or [])],
            answer=str(meta.get("answer", "") or "").strip(),
            explanation=str(meta.get("explanation", "") or ""),
            choices=[str(c) for c in (meta.get("choices") or [])],
            pin_last=int(meta.get("pin_last", 0) or 0),
            history=list(meta.get("history") or []),
            extra={k: v for k, v in meta.items() if k not in known},
        )
        return q

    # --------------------------------------------------------------- validation
    def problems(self) -> list[str]:
        """Static checks (no compile). Empty list means OK."""
        errs: list[str] = []
        if not NAME_RE.match(self.name):
            errs.append(f"nom de fichier non ASCII ou invalide : {self.name!r}")
        if self.type not in QUESTION_TYPES:
            errs.append(f"type inconnu {self.type!r} (developpement | conceptuel)")
        if not 1 <= self.difficulty <= 5:
            errs.append("difficulty doit être entre 1 et 5")
        if self.time_min <= 0:
            errs.append("time_min manquant")
        if self.points <= 0:
            errs.append("points manquant")
        for label, text in (("question", self.body), ("solution", self.solution_tex)):
            for _, ref in VREF_RE.findall(text):
                if ref not in self.variables:
                    errs.append(f"\\v{{{ref}}} dans la {label} n'est pas déclarée")
        if self.solution_mode == "manual" and not self.solution_tex.strip():
            errs.append(f"solution manuelle vide ou fichier {self.solution_file} manquant")
        numeric = {n for n, v in self.variables.items() if v.numeric}
        found: set[str] = set()
        for c in self.constraints:
            try:
                expr.parse(c, numeric)
            except expr.ExprError as exc:
                errs.append(f"contrainte {c!r} : {exc}")
        for p in self.parts:
            names = numeric | found
            if p.expr:
                try:
                    expr.parse(p.expr, names)
                except expr.ExprError as exc:
                    errs.append(f"partie {p.key} : {exc}")
            elif p.equation:
                if not p.find:
                    errs.append(f"partie {p.key} : 'find' manquant")
                elif "=" not in p.equation:
                    errs.append(f"partie {p.key} : l'équation doit contenir '='")
            if p.find and p.find in self.variables:
                errs.append(f"partie {p.key} : l'inconnue {p.find!r} porte le nom d'une variable")
            if p.find:
                found.add(p.find)
        if self.solution_mode in {"auto", "answers_only"} and not self.parts:
            errs.append(f"solution {self.solution_mode} sans 'parts'")
        if self.type == "conceptuel" and self.answer and not re.fullmatch(r"[A-Za-z]", self.answer):
            errs.append("answer doit être une lettre (A, B, C...)")
        if self.choices and "\\choices" not in self.body:
            errs.append("'choices' donné mais le marqueur \\choices est absent du .tex")
        return errs

    # ---------------------------------------------------------------- utilities
    @property
    def clean_body(self) -> str:
        return LEADING_SUBSECTION_RE.sub("", self.body, count=1)

    def meta_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "title": self.title,
            "type": self.type,
            "points": _intify(self.points),
            "time_min": _intify(self.time_min),
            "difficulty": self.difficulty,
            "figures": self.figures,
        }
        if self.tags:
            d["tags"] = self.tags
        if self.variables:
            d["variables"] = {k: v.to_dict() for k, v in self.variables.items()}
        if self.constraints:
            d["constraints"] = self.constraints
        sol: dict[str, Any] = {"mode": self.solution_mode}
        if self.solution_mode == "manual":
            sol["file"] = self.solution_file or f"{self.name}.sol.tex"
        if self.parts:
            sol["parts"] = {p.key: p.to_dict() for p in self.parts}
        d["solution"] = sol
        if self.type == "conceptuel":
            if self.answer:
                d["answer"] = self.answer
            if self.explanation:
                d["explanation"] = self.explanation
            if self.choices:
                d["choices"] = self.choices
            if self.pin_last:
                d["pin_last"] = self.pin_last
        d.update(self.extra)
        d["history"] = self.history
        return d

    def save(self, questions_root: Path) -> Path:
        folder = Path(questions_root) / self.course / self.topic
        folder.mkdir(parents=True, exist_ok=True)
        ypath = folder / f"{self.name}.yaml"
        ypath.write_text(yaml.safe_dump(self.meta_dict(), allow_unicode=True, sort_keys=False, width=1000),
                         encoding="utf-8")
        (folder / f"{self.name}.tex").write_text(self.body, encoding="utf-8")
        if self.solution_mode == "manual":
            (folder / (self.solution_file or f"{self.name}.sol.tex")).write_text(self.solution_tex, encoding="utf-8")
        self.path = ypath
        return ypath

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id, "course": self.course, "topic": self.topic, "name": self.name,
            "title": self.title, "type": self.type, "points": self.points, "time_min": self.time_min,
            "difficulty": self.difficulty, "solution_mode": self.solution_mode,
            "n_variables": len(self.variables), "tags": self.tags,
            "last_used": max((h.get("date", "") for h in self.history), default=""),
            "times_used": len(self.history),
            "needs_review": bool(self.extra.get("needs_review")),
        }


def _intify(x: float) -> float | int:
    return int(x) if float(x).is_integer() else x
