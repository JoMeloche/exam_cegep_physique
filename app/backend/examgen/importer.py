"""One-time importer for an existing hand-made LaTeX exam folder (read only).

Expected layout (Jo's SN3_examen1_automatique):
  main.tex, command.tex (A/B/C values in \\ifthenelse blocks), en-tete.tex,
  Question_dev/<topic>/*.tex, Question_concept/<topic>/*.tex, Solution/<topic>/*.tex, Figures/*
"""
from __future__ import annotations

import math
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from .expr import CONSTANTS, FUNCTIONS
from .library import Library
from .model import LEADING_SUBSECTION_RE, Question, Variable

TOPIC_MAP = {
    "MHS": "MHS",
    "Doppler": "Doppler",
    "Onde_progressive": "Onde_progressive",
    "Onde_sinusoidale": "Onde_sinusoidale",
    "Onde_stationnaire": "Onde_stationnaire",
    "Onde_resonnante": "Onde_stationnaire",
    "Intensite": "Intensite",
    "Puissance": "Intensite",
    "Battements": "Battements",
}
VERSIONS = ("A", "B", "C")
_KNOWN_LATEX = {
    "Alph", "Huge", "LARGE", "Large", "Delta", "Omega", "Theta", "Lambda", "Phi", "Psi", "Sigma", "Gamma", "Pi",
    "Rightarrow", "Leftarrow", "Leftrightarrow", "Longrightarrow",
}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def safe_name(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", strip_accents(s)).strip("_")
    return s or "question"


# ------------------------------------------------------------------ tiny TeX reader
def _read_group(text: str, i: int) -> tuple[str, int]:
    """text[i] must be '{'. Returns (content, index after closing brace)."""
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    if i >= len(text) or text[i] != "{":
        raise ValueError("groupe attendu")
    depth = 0
    start = i + 1
    j = i
    while j < len(text):
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "%":  # skip comment to end of line
            nl = text.find("\n", j)
            j = len(text) if nl < 0 else nl
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:j], j + 1
        j += 1
    raise ValueError("accolade non fermée")


def strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


_IF_RE = re.compile(r"\\ifthenelse\s*")
_EQ_RE = re.compile(r"\\equal\{\\(\w+)\}\{(\w+)\}")


def expand_version(text: str, letter: str) -> str:
    """Resolve every \\ifthenelse{\\equal{\\X}{L}}{then}{else} for the given version letter."""
    out = []
    i = 0
    while True:
        m = _IF_RE.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        try:
            cond, j = _read_group(text, m.end())
            then, j = _read_group(text, j)
            other, j = _read_group(text, j)
        except ValueError:
            out.append(text[m.start():])
            break
        em = _EQ_RE.search(cond)
        chosen = then if (em and em.group(2) == letter) else other
        out.append(expand_version(chosen, letter))
        i = j
    return "".join(out)


_NEWCMD_RE = re.compile(r"\\(?:re)?newcommand\s*\{?\\(\w+)\}?")


def parse_commands(text: str) -> dict[str, str]:
    cmds: dict[str, str] = {}
    for m in _NEWCMD_RE.finditer(text):
        try:
            val, _ = _read_group(text, m.end())
        except ValueError:
            continue
        cmds[m.group(1)] = val.strip()
    return cmds


def version_values(command_tex: str) -> dict[str, dict[str, str]]:
    """{macro: {A: value, B: value, C: value}}"""
    text = strip_comments(command_tex)
    res: dict[str, dict[str, str]] = {}
    for L in VERSIONS:
        for k, v in parse_commands(expand_version(text, L)).items():
            res.setdefault(k, {})[L] = v
    return res


# ------------------------------------------------------------------ variable inference
def _is_number(s: str) -> bool:
    return re.fullmatch(r"-?\d+(?:[.,]\d+)?", s.strip()) is not None


def _decimals(s: str) -> int:
    s = s.strip().replace(",", ".")
    return len(s.split(".")[1]) if "." in s else 0


def infer_variable(name: str, vals: dict[str, str], label: str) -> tuple[Variable, str]:
    raw = [vals[L] for L in VERSIONS if L in vals]
    if not raw:
        return Variable(name=name, type="text", values=["??"], label=label), "aucune valeur trouvée"
    if not all(_is_number(x) for x in raw):
        uniq = list(dict.fromkeys(raw))
        return Variable(name=name, type="text", values=uniq, label=label), "expression : liste de choix"
    nums = [float(x.replace(",", ".")) for x in raw]
    if len(set(nums)) == 1:
        v = nums[0]
        return Variable(name=name, type="choice", values=[int(v) if v.is_integer() else v], label=label), \
            "valeur identique dans A, B, C (valeur fixe)"
    dec = max(_decimals(x) for x in raw)
    unit = Fraction(1, 10 ** dec)
    fr = [Fraction(x.replace(",", ".")) for x in raw]
    step = unit
    for mult in (10, 5, 2):  # coarsest grid that still contains every original value
        cand = unit * mult
        if all((f / cand).denominator == 1 for f in fr):
            step = cand
            break
    lo, hi = min(nums), max(nums)
    spread = max(hi - lo, abs(hi) * 0.1)
    lo2, hi2 = lo - 0.1 * spread, hi + 0.1 * spread
    s = float(step)
    lo2 = math.floor(lo2 / s) * s
    hi2 = math.ceil(hi2 / s) * s
    if lo > 0 and lo2 <= 0:
        lo2 = s
    lo2, hi2 = round(lo2, dec), round(hi2, dec)
    note = f"intervalle déduit de A/B/C = {', '.join(raw)}"
    if dec == 0:
        return Variable(name=name, type="integer", min=int(lo2), max=int(hi2), step=int(s), label=label), note
    return Variable(name=name, type="decimal", min=lo2, max=hi2, step=round(s, dec), label=label), note


SI_FACTORS = {
    "g": (0.001, "kg"), "cm": (0.01, "m"), "mm": (0.001, "m"), "km": (1000.0, "m"), "ms": (0.001, "s"),
    "km/h": (1 / 3.6, "m/s"), "kHz": (1000.0, "Hz"), "g/m": (0.001, "kg/m"), "nm": (1e-9, "m"),
}


_CHOICES_RE = re.compile(r"\\begin\{enumerate\}\[label=\\Alph\*\)\](.*?)\\end\{enumerate\}", re.S)
PIN_RE = re.compile(r"^(aucun|toutes|tous|ces quantites|cela ne|impossible|la frequence sera la meme|rien)")


def extract_choices(body: str) -> tuple[str, list[str]]:
    """Turn an A) B) C) enumerate into a `choices` list + \\choices marker (enables shuffling)."""
    m = _CHOICES_RE.search(body)
    if not m:
        return body, []
    items = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"\\item\b", m.group(1))[1:]]
    if len(items) < 2 or any(not x for x in items):
        return body, []
    return body[:m.start()] + "\\choices" + body[m.end():], items


def pretty_title(stem: str) -> str:
    t = re.sub(r"^[QqCc]_", "", stem).replace("_", " ").strip()
    return t[:1].upper() + t[1:]


def guess_unit(text: str, var: str) -> str:
    v = re.escape(f"\\v{{{var}}}")
    for pat in (r"\\qty\{" + v + r"\}\{([^}]*)\}", v + r"\s*\\text\{\s*([^}]*)\}", v + r"\s*\\,\s*\\mathrm\{([^}]*)\}"):
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return ""


def short_names(macros: list[str]) -> dict[str, str]:
    if len(macros) < 2:
        return {m: m for m in macros}
    pre = macros[0]
    for m in macros[1:]:
        while not m.startswith(pre):
            pre = pre[:-1]
    # cut back to a camel-case boundary so the rest starts with an uppercase letter
    while pre and any(len(m) <= len(pre) or not m[len(pre)].isupper() for m in macros):
        pre = pre[:-1]
    out = {}
    for m in macros:
        s = m[len(pre):] if pre else m
        if not s or s in CONSTANTS or s in FUNCTIONS or not re.match(r"^[A-Za-z]", s):
            s = m
        out[m] = s
    if len(set(out.values())) != len(out):
        return {m: m for m in macros}
    return out


# ------------------------------------------------------------------ main import
@dataclass
class ImportReport:
    imported: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    figures: list[str] = field(default_factory=list)
    notes: dict[str, list[str]] = field(default_factory=dict)

    def note(self, qid: str, msg: str) -> None:
        self.notes.setdefault(qid, []).append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {"imported": self.imported, "skipped": self.skipped, "figures": self.figures, "notes": self.notes}


def _solution_pairs(main_tex: str) -> dict[str, str]:
    """question path -> solution path, from consecutive uncommented \\input lines in main.tex."""
    inputs = re.findall(r"^[ \t]*\\input\{([^}]*)\}", main_tex, re.M)
    pairs = {}
    for a, b in zip(inputs, inputs[1:]):
        if b.startswith("Solution/") and not a.startswith("Solution/"):
            pairs[_norm(a)] = _norm(b)
    return pairs


def _norm(p: str) -> str:
    p = p.strip()
    return p if p.endswith(".tex") else p + ".tex"


def import_folder(src: Path, lib: Library, *, course: str, overwrite: bool = False) -> ImportReport:
    src = Path(src)
    lib.ensure()
    rep = ImportReport()
    cmd_path = src / "command.tex"
    values = version_values(cmd_path.read_text(encoding="utf-8")) if cmd_path.exists() else {}
    main = (src / "main.tex").read_text(encoding="utf-8") if (src / "main.tex").exists() else ""
    pairs = _solution_pairs(main)

    # figures
    fig_dir = src / "Figures"
    if fig_dir.exists():
        lib.figures_dir.mkdir(parents=True, exist_ok=True)
        for f in sorted(fig_dir.iterdir()):
            if f.is_file():
                dest = lib.figures_dir / f.name
                if overwrite or not dest.exists():
                    shutil.copy2(f, dest)
                rep.figures.append(f.name)

    macro_re = re.compile(r"\\([A-Za-z]+)(?![A-Za-z])")
    seen_names: dict[tuple[str, str], str] = {}
    for kind, folder in (("developpement", "Question_dev"), ("conceptuel", "Question_concept")):
        base = src / folder
        if not base.exists():
            continue
        for tex in sorted(base.glob("*/*.tex")):
            rel = tex.relative_to(src).as_posix()
            topic_src = safe_name(tex.parent.name)
            topic = TOPIC_MAP.get(topic_src, topic_src)
            name = safe_name(re.sub(r"^[QqCc]_", "", tex.stem))
            if (topic, name) in seen_names:
                name = f"{name}_{'c' if kind == 'conceptuel' else 'd'}"
            seen_names[(topic, name)] = rel
            qid = f"{course}/{topic}/{name}"
            dest_yaml = lib.questions_dir / course / topic / f"{name}.yaml"
            if dest_yaml.exists() and not overwrite:
                rep.skipped.append(f"{qid} (existe déjà)")
                continue
            body = tex.read_text(encoding="utf-8")
            used = []
            for m in macro_re.finditer(strip_comments(body)):
                n = m.group(1)
                if n in values and n not in used:
                    used.append(n)
            sol_rel = pairs.get(rel)
            sol_text = ""
            if sol_rel and (src / sol_rel).exists():
                sol_text = (src / sol_rel).read_text(encoding="utf-8")
                for m in macro_re.finditer(strip_comments(sol_text)):
                    n = m.group(1)
                    if n in values and n not in used:
                        used.append(n)
            names = short_names(used)
            variables: dict[str, Variable] = {}
            originals: dict[str, list[str]] = {}
            for macro in used:
                var, note = infer_variable(names[macro], values[macro], label=macro)
                variables[var.name] = var
                originals[var.name] = [values[macro].get(L, "") for L in VERSIONS]
                if "déduit" not in note:
                    rep.note(qid, f"{var.name}: {note}")

            def sub(text: str) -> str:
                for macro in sorted(used, key=len, reverse=True):
                    text = re.sub(r"\\" + macro + r"(?![A-Za-z])(\{\})?", lambda _m, n=names[macro]: f"\\v{{{n}}}", text)
                return text

            new_body = sub(body)
            for vname, var in variables.items():
                if not var.unit:
                    var.unit = guess_unit(new_body + "\n" + sub(sol_text), vname)
                if var.unit in SI_FACTORS and var.si == 1.0:
                    var.si, var.si_unit = SI_FACTORS[var.unit]
            choices: list[str] = []
            pin_last = 0
            if kind == "conceptuel":
                new_body = LEADING_SUBSECTION_RE.sub("", new_body, count=1)
                new_body, choices = extract_choices(new_body)
                if choices and PIN_RE.search(strip_accents(choices[-1]).lower()):
                    pin_last = 1
            leftovers = sorted({m.group(1) for m in macro_re.finditer(strip_comments(new_body))
                                if re.match(r"^(?:[a-z]+[A-Z]|[A-Z][a-z]+[A-Z])", m.group(1))
                                and m.group(1) not in _KNOWN_LATEX})
            for lo in leftovers:
                rep.note(qid, f"macro \\{lo} sans valeur dans command.tex (à remplacer à la main)")
            figures = sorted({Path(f).name for f in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", body)})
            meta: dict[str, Any] = {
                "title": pretty_title(tex.stem),
                "type": kind,
                "points": 20 if kind == "developpement" else 4,
                "time_min": 20 if kind == "developpement" else 4,
                "difficulty": 3 if kind == "developpement" else 2,
                "figures": figures,
                "variables": {},
                "solution": {"mode": "manual", "file": f"{name}.sol.tex"} if sol_text else {"mode": "none"},
                "needs_review": True,
                "source": rel,
            }
            if originals:
                meta["original_values"] = {k: dict(zip(VERSIONS, v)) for k, v in originals.items()}
            meta["variables"] = {k: v.to_dict() for k, v in variables.items()}
            if choices:
                meta["choices"] = choices
                if pin_last:
                    meta["pin_last"] = pin_last
            q = Question.from_dict(qid, meta, new_body, solution_tex=sub(sol_text) if sol_text else "")
            if kind == "conceptuel":
                rep.note(qid, "réponse (answer) à indiquer")
            if not sol_text and kind == "developpement":
                rep.note(qid, "aucune solution : à écrire ou passer en mode automatique")
            if used:
                rep.note(qid, "intervalles déduits des versions A/B/C : à vérifier")
            rep.note(qid, "temps et difficulté par défaut : à ajuster")
            lib.save_question(q)
            rep.imported.append(qid)
    return rep
