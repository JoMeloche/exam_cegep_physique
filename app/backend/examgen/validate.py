"""Library validation: static checks, value drawing, solving, and an optional compile per question."""
from __future__ import annotations

import random
import tempfile
from pathlib import Path

from . import values as V
from .latex import LatexError
from .library import Library
from .model import Question
from .solve import SolveError, solve_parts


def validate_question(lib: Library, q: Question, *, compile_check: bool = True, draws: int = 3) -> list[str]:
    errs = list(q.problems())
    missing_figs = [f for f in q.figures if not (lib.figures_dir / Path(f).name).exists()]
    errs += [f"figure introuvable : {f}" for f in missing_figs]
    if errs:
        return errs
    rng = random.Random(12345)
    sets = []
    for _ in range(draws):
        try:
            sets.append(V.draw(q, rng, avoid=sets))
        except V.DrawError as exc:
            return [str(exc)]
    if q.parts:
        extra_rng = random.Random(777)
        more = sets + [V.draw(q, extra_rng) for _ in range(max(0, 20 - len(sets)))]
        per_part: dict[str, list[tuple[float, dict]]] = {}
        for vals in more:
            try:
                res = solve_parts(q, vals, with_latex=q.solution_mode in {"auto", "answers_only"})
            except (SolveError, Exception) as exc:  # noqa: BLE001
                errs.append(f"calcul de la solution : {exc}")
                break
            for r in res:
                per_part.setdefault(r.key, []).append((r.value, vals))
        for key, items in per_part.items():
            scale = max(abs(v) for v, _ in items)
            for v, vals in items:
                if scale and abs(v) < 1e-9 * scale:
                    shown = ", ".join(f"{k} = {V.fmt_plain(x) if not isinstance(x, str) else x}" for k, x in vals.items())
                    errs.append(f"réponse quasi nulle (partie {key}) pour {shown} : ajoutez une contrainte")
                    break
    if compile_check and not errs:
        from .generate import preview_question
        with tempfile.TemporaryDirectory() as tmp:
            try:
                preview_question(lib, q, seed=12345, n=draws, workdir=Path(tmp))
            except LatexError as exc:
                errs.append(str(exc))
                if exc.log_excerpt:
                    errs.append(exc.log_excerpt.strip().splitlines()[0][:300])
    return errs


def validate_library(lib: Library, *, compile_check: bool = True, draws: int = 3, course: str | None = None,
                     only: str | None = None) -> dict[str, list[str]]:
    report: dict[str, list[str]] = {}
    for path, err in lib.load_errors.items():
        report[path] = [err]
    for q in lib.questions(course=course):
        if only and not q.id.startswith(only):
            continue
        report[q.id] = validate_question(lib, q, compile_check=compile_check, draws=draws)
    return report
