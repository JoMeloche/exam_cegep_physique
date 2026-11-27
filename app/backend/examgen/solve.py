"""Automatic solutions with SymPy: isolate the unknown and write Jo's five-step layout."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sympy as sp

from . import expr
from .model import Part, Question
from .values import fmt_plain, fmt_sig, round_sig, si_values

CONSTANT_INFO = {
    "g": ("Accélération gravitationnelle", "g", "m/s^2"),
    "c": ("Vitesse de la lumière", "c", "m/s"),
    "h": ("Constante de Planck", "h", "J.s"),
    "e": ("Charge élémentaire", "e", "C"),
    "k_B": ("Constante de Boltzmann", "k_B", "J/K"),
    "sigma": ("Constante de Stefan-Boltzmann", r"\sigma", "W/(m^2.K^4)"),
    "I0": ("Intensité de référence", "I_0", "W/m^2"),
    "m_e": ("Masse de l'électron", "m_e", "kg"),
    "N_A": ("Nombre d'Avogadro", "N_A", "mol^{-1}"),
}

_SP_FUNCS = {
    "sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "asin": sp.asin, "acos": sp.acos,
    "atan": sp.atan, "exp": sp.exp, "log": sp.log, "ln": sp.log, "log10": lambda x: sp.log(x, 10),
    "abs": sp.Abs, "pi": sp.pi, "floor": sp.floor, "ceil": sp.ceiling, "deg": lambda x: x * 180 / sp.pi, "rad": lambda x: x * sp.pi / 180,
}


class SolveError(ValueError):
    pass


def tidy(e: sp.Expr) -> sp.Expr:
    """Display form: merge sqrt(2)*sqrt(E/k) into sqrt(2E/k), recursively."""
    if not isinstance(e, sp.Basic) or e.is_Atom:
        return e
    args = [tidy(a) for a in e.args]
    if e.is_Mul:
        roots = [f for f in args if f.is_Pow and f.exp == sp.S.Half]
        if len(roots) > 1:
            rest = [f for f in args if f not in roots]
            inner = sp.together(sp.Mul(*[r.base for r in roots]))
            r = sp.Pow(inner, sp.S.Half, evaluate=False)
            return sp.Mul(*rest, r, evaluate=False) if rest else r
    try:
        return e.func(*args, evaluate=False)
    except TypeError:
        return e.func(*args)


def fr_num(txt: str) -> str:
    """Decimal comma for math mode (siunitx handles it inside \\qty)."""
    return txt.replace(".", "{,}")


@dataclass
class PartResult:
    key: str
    name: str
    value: float
    unit: str
    latex: str = ""


def _sym_latex(name: str, q: Question, part_symbols: dict[str, str]) -> str:
    if name in q.variables and q.variables[name].symbol:
        return q.variables[name].symbol
    if name in part_symbols:
        return part_symbols[name]
    if name in CONSTANT_INFO:
        return CONSTANT_INFO[name][1]
    return sp.latex(sp.Symbol(name))


def _sympify(src: str, names: set[str]) -> sp.Expr:
    expr.parse(src, names)  # whitelist check before handing to SymPy
    local = dict(_SP_FUNCS)
    local.update({n: sp.Symbol(n) for n in names})
    return sp.sympify(src.strip().replace("^", "**"), locals=local)


def _pick_root(sols: list[sp.Expr], subs: dict[sp.Symbol, float], how: str) -> tuple[sp.Expr, float]:
    vals = []
    for s in sols:
        v = complex(sp.N(s.subs(subs)))
        if abs(v.imag) < 1e-9 * max(1.0, abs(v.real)):
            vals.append((s, v.real))
    if not vals:
        raise SolveError("aucune solution réelle")
    if how == "negative":
        neg = [x for x in vals if x[1] < 0]
        return (neg or vals)[0]
    if how == "max":
        return max(vals, key=lambda x: x[1])
    if how == "min":
        return min(vals, key=lambda x: x[1])
    if how.isdigit():
        return vals[min(int(how), len(vals) - 1)]
    pos = [x for x in vals if x[1] >= 0]
    return (pos or vals)[0]


def _qty(value: str, unit: str) -> str:
    return rf"\qty{{{value}}}{{{unit}}}" if unit else rf"\num{{{value}}}"


def solve_parts(q: Question, values: dict[str, Any], *, with_latex: bool = True) -> list[PartResult]:
    """Compute every part. For mode auto also builds the step-by-step LaTeX."""
    env = si_values(q, values)
    numeric = set(env)
    found: dict[str, float] = {}
    found_units: dict[str, str] = {}
    part_symbols: dict[str, str] = {}
    results: list[PartResult] = []
    for p in q.parts:
        names = numeric | set(found)
        if p.expr:
            val = float(expr.evaluate(p.expr, {**env, **found}))
            latex = _answers_only_latex(q, p, val) if with_latex else ""
        elif p.equation and p.find:
            val, latex = _solve_equation(q, p, env, found, found_units, part_symbols, names, with_latex)
        else:
            continue
        name = p.find or p.key
        if name not in env:  # never let a part result shadow a given variable
            found[name] = val
        found_units[name] = p.unit
        if p.symbol:
            part_symbols[name] = p.symbol
        results.append(PartResult(p.key, name, val, p.unit, latex))
    return results


def _answers_only_latex(q: Question, p: Part, val: float) -> str:
    label = p.label or (p.find or "Réponse")
    return (rf"\textbf{{{p.key})}} {label} : \textbf{{{_qty(fmt_sig(val, p.sigfigs), p.unit)}}}" "\n\n")


def _solve_equation(q, p: Part, env, found, found_units, part_symbols, names, with_latex):
    names = names | {p.find}
    lhs, rhs = p.equation.split("=", 1)
    try:
        L = _sympify(lhs, names)
        R = _sympify(rhs, names)
    except (expr.ExprError, sp.SympifyError) as exc:
        raise SolveError(f"partie {p.key}: {exc}") from exc
    unknown = sp.Symbol(p.find)
    eq = sp.Eq(L, R)
    sols = sp.solve(eq, unknown)
    if not sols:
        raise SolveError(f"partie {p.key}: SymPy ne peut pas isoler {p.find}")
    known = {**env, **found}
    from .expr import CONSTANTS
    subs = {sp.Symbol(n): v for n, v in known.items()}
    used_consts = [c for c in CONSTANTS if c not in known and sp.Symbol(c) in eq.free_symbols]
    subs.update({sp.Symbol(c): CONSTANTS[c] for c in used_consts})
    sol_expr, val = _pick_root(sols, subs, p.root)
    if not with_latex:
        return val, ""

    sym_names = {sp.Symbol(n): _sym_latex(n, q, part_symbols) for n in names | set(used_consts)}
    sym_names[unknown] = p.symbol or _sym_latex(p.find, q, part_symbols)
    lat = lambda e: sp.latex(e, symbol_names=sym_names)  # noqa: E731

    # numbers substituted into the isolated expression
    num_names = {}
    for s in sol_expr.free_symbols:
        n = s.name
        if n in env:
            num_names[s] = fmt_plain(round_sig(env[n], 6))
        elif n in found:
            num_names[s] = fmt_sig(found[n], 4)
        elif n in CONSTANTS:
            num_names[s] = fmt_sig(CONSTANTS[n], 4)
        if s in num_names:
            txt = num_names[s]
            if "e" in txt:
                m, ex = txt.split("e")
                txt = rf"{fr_num(m)} \times 10^{{{int(ex)}}}"
            else:
                txt = fr_num(txt)
            num_names[s] = rf"\left({txt}\right)" if txt.startswith("-") or "times" in txt else txt
    shown = tidy(sol_expr)
    numeric_latex = sp.latex(shown, symbol_names=num_names)

    label = p.label or p.find
    target_unit = p.unit
    lines = [rf"\subsubsection*{{Question {p.key}) {label}}}", r"\begin{enumerate}[label=\arabic*)]",
             r"    \item \textbf{Variables connues et recherchées :}", r"    \begin{itemize}[label= -]"]
    for s in sorted(eq.free_symbols - {unknown}, key=lambda s: s.name):
        n = s.name
        if n in q.variables:
            v = q.variables[n]
            given = _qty(fmt_plain(values_display(q, n, env)), v.unit)
            conv = ""
            if v.si != 1.0:
                conv = " = " + _qty(fmt_plain(round_sig(env[n], 6)), v.si_unit or "")
            lines.append(rf"        \item {v.label or n} : ${sym_names[s]} = {given}{conv}$")
        elif n in found:
            lines.append(rf"        \item {n} (trouvé précédemment) : ${sym_names[s]} = {_qty(fmt_sig(found[n], 4), found_units.get(n, ''))}$")
        elif n in CONSTANT_INFO:
            cl, _, cu = CONSTANT_INFO[n]
            lines.append(rf"        \item {cl} : ${sym_names[s]} = {_qty(fmt_sig(CONSTANTS[n], 4), cu)}$")
    unit_txt = rf" \text{{ ({target_unit})}}" if target_unit else ""
    lines.append(rf"        \item Variable recherchée : {label} ${sym_names[unknown]}{unit_txt}$")
    lines.append(r"    \end{itemize}")
    lines.append(r"    \item \textbf{Équations pertinentes :}")
    lines.append(rf"    \[ {lat(L)} = {lat(R)} \]")
    lines.append(r"    \item \textbf{Isolation de la variable recherchée :}")
    lines.append(rf"    \[ {sym_names[unknown]} = {lat(shown)} \]")
    lines.append(r"    \item \textbf{Résolution numérique :}")
    lines.append(rf"    \[ {sym_names[unknown]} = {numeric_latex} = {_qty(fmt_sig(val, 4), target_unit)} \]")
    lines.append(r"    \item \textbf{Réponse :}")
    lines.append(rf"    {label} : \textbf{{{_qty(fmt_sig(val, p.sigfigs), target_unit)}}}.")
    lines.append(r"\end{enumerate}")
    return val, "\n".join(lines) + "\n"


def values_display(q: Question, name: str, env: dict[str, float]) -> float:
    v = q.variables[name]
    return round_sig(env[name] / v.si, 10) if v.si else env[name]


def auto_solution_tex(q: Question, values: dict[str, Any]) -> str:
    return "\n".join(r.latex for r in solve_parts(q, values))
