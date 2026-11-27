"""Safe evaluation of user expressions (constraints, formulas).

Expressions are parsed with :mod:`ast` and only a small whitelist of node types,
functions and names is accepted, so a question file can never run arbitrary code.
"""
from __future__ import annotations

import ast
import math
from typing import Any, Mapping

FUNCTIONS: dict[str, Any] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "exp": math.exp,
    "log": math.log,
    "ln": math.log,
    "log10": math.log10,
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "deg": math.degrees,
    "rad": math.radians,
}

CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "g": 9.81,
    "c": 3.0e8,
    "h": 6.626e-34,
    "e": 1.602e-19,
    "k_B": 1.381e-23,
    "sigma": 5.67e-8,
    "I0": 1.0e-12,
    "m_e": 9.109e-31,
    "N_A": 6.022e23,
}

_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
    ast.Call, ast.Name, ast.Load, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
)


class ExprError(ValueError):
    pass


def _check(tree: ast.AST, names: set[str]) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ExprError(f"élément non permis : {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                raise ExprError("fonction non permise")
            if node.keywords:
                raise ExprError("arguments nommés non permis")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, bool)):
            raise ExprError("seuls les nombres sont permis")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in names and node.id not in FUNCTIONS and node.id not in CONSTANTS:
                raise ExprError(f"nom inconnu : {node.id}")


def parse(source: str, names: set[str]) -> ast.Expression:
    src = source.strip().replace("^", "**")
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as exc:  # pragma: no cover - message only
        raise ExprError(f"syntaxe invalide : {source!r}") from exc
    _check(tree, names)
    return tree


def evaluate(source: str, values: Mapping[str, float]) -> Any:
    tree = parse(source, set(values))
    env: dict[str, Any] = {**CONSTANTS, **FUNCTIONS, **values}
    code = compile(tree, "<expr>", "eval")
    try:
        return eval(code, {"__builtins__": {}}, env)  # noqa: S307 - AST whitelisted above
    except (ZeroDivisionError, ValueError, OverflowError, TypeError) as exc:
        raise ExprError(f"{source!r} : {exc}") from exc


def names_in(source: str) -> set[str]:
    tree = ast.parse(source.strip().replace("^", "**"), mode="eval")
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in FUNCTIONS}
