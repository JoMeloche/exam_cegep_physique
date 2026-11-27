"""Drawing variable values and formatting numbers for LaTeX."""
from __future__ import annotations

import math
import random
from decimal import Decimal
from typing import Any

from . import expr
from .model import Question, Variable


class DrawError(RuntimeError):
    pass


def _decimals_of(x: float) -> int:
    d = Decimal(repr(float(x))).normalize()
    exp = d.as_tuple().exponent
    return max(0, -exp) if isinstance(exp, int) else 0


def round_sig(x: float, sig: int = 3) -> float:
    if x == 0 or not math.isfinite(x):
        return x
    return round(x, sig - 1 - int(math.floor(math.log10(abs(x)))))


def fmt_plain(x: Any, decimals: int | None = None) -> str:
    """Plain decimal string, never scientific notation, no trailing zeros unless `decimals`."""
    if isinstance(x, str):
        return x
    if isinstance(x, bool):
        return str(int(x))
    if isinstance(x, int):
        return str(x)
    x = float(x)
    if decimals is not None:
        s = f"{x:.{decimals}f}"
    else:
        s = format(Decimal(repr(x)).normalize(), "f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
    if s in {"-0", "-0.0"} or (s.startswith("-") and float(s) == 0):
        s = s[1:]
    return s


def fmt_sig(x: float, sig: int = 3) -> str:
    """Number with `sig` significant figures, for siunitx (uses e-notation for very small/large)."""
    if not math.isfinite(x):
        return "\\text{indéfini}"
    if x == 0:
        return "0"
    mag = int(math.floor(math.log10(abs(x))))
    if mag < -3 or mag >= 6:
        mant = x / 10 ** mag
        mant_s = f"{mant:.{sig - 1}f}"
        if float(mant_s) >= 10:  # rounding overflow (9.999 -> 10.0)
            mag += 1
            mant_s = f"{x / 10 ** mag:.{sig - 1}f}"
        return f"{mant_s}e{mag}"
    decimals = max(0, sig - 1 - mag)
    return f"{x:.{decimals}f}"


def draw_variable(v: Variable, rng: random.Random) -> Any:
    if v.type == "text":
        return rng.choice(v.values)
    if v.type == "choice":
        return rng.choice(v.values)
    lo, hi = float(v.min), float(v.max)
    if v.type == "integer":
        step = int(v.step or 1)
        n = int((hi - lo) // step)
        return int(round(lo + step * rng.randint(0, max(n, 0))))
    if v.type == "sigfig":
        return round_sig(rng.uniform(lo, hi), v.sigfigs)
    # decimal
    if v.step:
        n = int(math.floor((hi - lo) / v.step + 1e-9))
        dec = max(_decimals_of(v.step), _decimals_of(lo))
        return round(lo + v.step * rng.randint(0, max(n, 0)), dec)
    dec = 2 if v.decimals is None else int(v.decimals)
    return round(rng.uniform(lo, hi), dec)


def display_decimals(v: Variable) -> int | None:
    """Fixed number of decimals for display, so 0.30 prints as 0.30 when step is 0.05."""
    if v.type == "decimal":
        if v.decimals is not None:
            return int(v.decimals)
        if v.step:
            return max(_decimals_of(v.step), _decimals_of(v.min or 0))
    return None


def si_values(q: Question, values: dict[str, Any]) -> dict[str, float]:
    return {n: float(values[n]) * q.variables[n].si for n in q.variables if q.variables[n].numeric}


def constraints_ok(q: Question, values: dict[str, Any]) -> bool:
    if not q.constraints:
        return True
    env = si_values(q, values)
    for c in q.constraints:
        try:
            if not expr.evaluate(c, env):
                return False
        except expr.ExprError:
            return False
    return True


def _fpeval_groups(text: str) -> list[str]:
    out = []
    i = 0
    key = "\\fpeval"
    while True:
        j = text.find(key, i)
        if j < 0:
            return out
        k = j + len(key)
        while k < len(text) and text[k] in " \t\n":
            k += 1
        if k >= len(text) or text[k] != "{":
            i = k
            continue
        depth, start = 0, k
        while k < len(text):
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        out.append(text[start + 1:k])
        i = k + 1


def _fp_value(src: str) -> float | None:
    """Evaluate an \\fpeval body; nested \\fpeval are evaluated first. None = cannot check."""
    inner = _fpeval_groups(src)
    for g in inner:
        v = _fp_value(g)
        if v is None:
            return None
        src = src.replace("\\fpeval{" + g + "}", repr(v))
    try:
        return float(expr.evaluate(src.replace("{", "(").replace("}", ")"), {}))
    except expr.ExprError as exc:
        msg = str(exc)
        if "nom inconnu" in msg or "fonction non permise" in msg or "syntaxe" in msg or "élément" in msg:
            return None  # something we do not understand: let LaTeX decide
        raise


def fpeval_ok(q: Question, values: dict[str, Any]) -> bool:
    """Reject value sets for which an \\fpeval in the question or solution has no real value."""
    text = q.body + "\n" + q.solution_tex
    if "\\fpeval" not in text:
        return True
    from .latex import substitute
    text = substitute(text, formatted(q, values), formatted_si(q, values))
    for g in _fpeval_groups(text):
        try:
            _fp_value(g)
        except expr.ExprError:
            return False
    return True


def draw(q: Question, rng: random.Random, *, avoid: list[dict[str, Any]] | None = None,
         max_tries: int = 2000) -> dict[str, Any]:
    """Draw one value set satisfying every constraint and differing from every set in `avoid`."""
    avoid = avoid or []
    if not q.variables:
        return {}
    fallback: dict[str, Any] | None = None
    for _ in range(max_tries):
        values = {n: draw_variable(v, rng) for n, v in q.variables.items()}
        if not constraints_ok(q, values) or not fpeval_ok(q, values):
            continue
        if fallback is None:
            fallback = values
        if all(values != a for a in avoid):
            return values
    if fallback is not None:
        return fallback  # space too small to be unique: accept a repeat rather than fail
    raise DrawError(f"{q.id}: aucune combinaison ne respecte les contraintes après {max_tries} essais")


def formatted(q: Question, values: dict[str, Any]) -> dict[str, str]:
    out = {}
    for n, v in q.variables.items():
        out[n] = fmt_plain(values[n], display_decimals(v))
    return out


def formatted_si(q: Question, values: dict[str, Any]) -> dict[str, str]:
    out = {}
    for n, v in q.variables.items():
        if v.numeric:
            out[n] = fmt_plain(round_sig(float(values[n]) * v.si, 12))
        else:
            out[n] = str(values[n])
    return out
