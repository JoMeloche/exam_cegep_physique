"""LaTeX: value substitution, finding the TeX engine, compiling with useful errors."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .model import VREF_RE

MARKER = "%%EXAMGEN-QUESTION "

# Web server with accounts: TeX runs with the server's own engine (the per-user "latex.path" setting
# is ignored), never with unrestricted shell escape, and cannot read or write files outside its
# working directory (openin_any/openout_any = paranoid), so one user's LaTeX can't read other banks.
RESTRICTED = False
ALLOWED_ENGINES = {"pdflatex", "xelatex", "lualatex"}


class LatexError(RuntimeError):
    def __init__(self, message: str, log_excerpt: str = "", question_id: str | None = None):
        super().__init__(message)
        self.log_excerpt = log_excerpt
        self.question_id = question_id


def substitute(text: str, display: dict[str, str], si: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        kind, name = m.group(1), m.group(2)
        table = display if kind == "v" else si
        if name not in table:
            return m.group(0)
        return table[name]
    return VREF_RE.sub(repl, text)


def fill(template: str, fields: dict[str, str]) -> str:
    return re.sub(r"<<(\w+)>>", lambda m: str(fields.get(m.group(1), "")), template)


def render_choices(choices: list[str]) -> str:
    items = "\n".join(f"    \\item {c}" for c in choices)
    return "\\begin{enumerate}[label=\\Alph*)]\n" + items + "\n\\end{enumerate}"


# ----------------------------------------------------------------- engine lookup
def _bundled_dirs() -> list[Path]:
    """Where a bundled TinyTeX may live (PyInstaller app dir, next to the package, ~/exam_app)."""
    bases = []
    if getattr(sys, "frozen", False):
        bases.append(Path(sys.executable).parent)
        if hasattr(sys, "_MEIPASS"):
            bases.append(Path(sys._MEIPASS))  # type: ignore[attr-defined]
    bases.append(Path(__file__).resolve().parent.parent)
    bases.append(Path.home() / "exam_app")
    out = []
    for b in bases:
        for sub in ("tinytex/bin/windows", "tinytex/bin/win32", "tinytex/bin/x86_64-linux",
                    "tinytex/bin/universal-darwin", "tinytex/bin/x86_64-darwin", "TinyTeX/bin/windows"):
            out.append(b / sub)
    return out


def find_engine(engine: str = "pdflatex", configured_path: str = "") -> str | None:
    exe = engine + (".exe" if os.name == "nt" else "")
    if configured_path:
        p = Path(configured_path).expanduser()
        if p.is_file():
            return str(p)
        if (p / exe).exists():
            return str(p / exe)
    env = os.environ.get("EXAMGEN_TEX")
    if env and (Path(env) / exe).exists():
        return str(Path(env) / exe)
    for d in _bundled_dirs():
        try:
            if (d / exe).exists():
                return str(d / exe)
        except OSError:  # e.g. a home folder this user may not read
            continue
    return shutil.which(engine)


@dataclass
class CompileResult:
    pdf: Path
    log: str


_ERR_RE = re.compile(r"^(?:\./)?[^:\n]*\.tex:(\d+): (.*)$", re.M)


def _question_at_line(tex: str, line_no: int) -> str | None:
    current = None
    for i, line in enumerate(tex.splitlines(), start=1):
        if i > line_no:
            break
        if line.startswith(MARKER):
            current = line[len(MARKER):].strip() or None
    return current


def compile_tex(tex: str, workdir: Path, jobname: str, *, engine: str = "pdflatex",
                engine_path: str = "", runs: int = 2, timeout: int = 120) -> CompileResult:
    env = None
    if RESTRICTED:
        engine = engine if engine in ALLOWED_ENGINES else "pdflatex"
        engine_path = ""
        env = {**os.environ, "openin_any": "p", "openout_any": "p", "shell_escape": "p"}
    exe = find_engine(engine, engine_path)
    if not exe:
        raise LatexError("Aucune installation LaTeX trouvée. Indiquez le chemin dans Paramètres.")
    workdir.mkdir(parents=True, exist_ok=True)
    src = workdir / f"{jobname}.tex"
    src.write_text(tex, encoding="utf-8")
    log = ""
    for _ in range(runs):
        proc = subprocess.run(
            [exe, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", src.name],
            cwd=workdir, capture_output=True, timeout=timeout, env=env,
        )
        logp = workdir / f"{jobname}.log"
        log = logp.read_text(encoding="utf-8", errors="replace") if logp.exists() else proc.stdout.decode(errors="replace")
        if proc.returncode != 0:
            m = _ERR_RE.search(log)
            qid = None
            msg = "Erreur LaTeX"
            excerpt = log[-3000:]
            if m:
                line_no = int(m.group(1))
                qid = _question_at_line(tex, line_no)
                msg = f"Erreur LaTeX ligne {line_no} : {m.group(2)}"
                start = max(0, m.start() - 200)
                excerpt = log[start:m.end() + 800]
            elif "!" in log:
                i = log.index("!")
                excerpt = log[i:i + 1000]
                msg = "Erreur LaTeX : " + log[i:].splitlines()[0]
            if qid:
                msg += f" (question {qid})"
            raise LatexError(msg, excerpt, qid)
    pdf = workdir / f"{jobname}.pdf"
    if not pdf.exists():
        raise LatexError("La compilation n'a produit aucun PDF", log[-3000:])
    return CompileResult(pdf, log)
