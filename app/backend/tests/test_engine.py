import datetime as dt
import random

from examgen import values as V
from examgen.expr import ExprError, evaluate
from examgen.generate import date_long_fr, duration_text, exam_basename, session_code
from examgen.importer import expand_version, infer_variable, parse_commands, short_names
from examgen.model import Question
from examgen.solve import solve_parts


def q(meta, body="x"):
    return Question.from_dict("C/T/n", meta, body)


def test_naming():
    d = dt.date(2026, 9, 28)
    assert exam_basename("203-SN3-RE", 1, d, 1) == "203-SN3-RE_Examen_1_A26_v1"
    assert session_code(dt.date(2027, 1, 10)) == "H27"
    assert session_code(dt.date(2027, 7, 1)) == "E27"
    assert date_long_fr(d) == "28 septembre 2026"
    assert duration_text(120) == "2 h" and duration_text(150) == "2 h 30"


def test_expr_is_sandboxed():
    assert evaluate("sqrt(x)*2", {"x": 4}) == 4
    for bad in ("__import__('os')", "x.__class__", "[1,2]", "open('f')", "lambda: 1"):
        try:
            evaluate(bad, {"x": 1})
        except ExprError:
            continue
        raise AssertionError(bad)


def test_draw_respects_constraints_and_uniqueness():
    qq = q({"variables": {"a": {"type": "integer", "min": 1, "max": 10}, "b": {"type": "integer", "min": 1, "max": 10}},
            "constraints": ["a > b"]})
    rng = random.Random(1)
    seen = []
    for _ in range(5):
        v = V.draw(qq, rng, avoid=seen)
        assert v["a"] > v["b"] and v not in seen
        seen.append(v)


def test_decimal_display_keeps_step_decimals():
    qq = q({"variables": {"E": {"type": "decimal", "min": 0.1, "max": 0.4, "step": 0.05}}})
    assert V.formatted(qq, {"E": 0.3}) == {"E": "0.30"}
    assert V.fmt_plain(0.000012) == "0.000012"


def test_fpeval_domain_rejected():
    qq = Question.from_dict("C/T/n", {"variables": {"x": {"type": "integer", "min": -5, "max": 5}}},
                            r"$\fpeval{sqrt(\v{x})}$")
    rng = random.Random(3)
    for _ in range(20):
        assert V.draw(qq, rng)["x"] >= 0


def test_auto_solution_with_si_conversion():
    qq = q({"variables": {"E": {"type": "decimal", "min": 0.2, "max": 0.2, "step": 0.1, "unit": "J"},
                          "m": {"type": "integer", "min": 200, "max": 200, "unit": "g", "si": "0.001 kg"}},
            "solution": {"mode": "auto", "parts": {"a": {"find": "v", "equation": "E = m*v**2/2", "unit": "m/s"}}}})
    (r,) = solve_parts(qq, {"E": 0.2, "m": 200})
    assert abs(r.value - (2 * 0.2 / 0.2) ** 0.5) < 1e-9
    assert "Isolation" in r.latex and r"\qty{1.41}{m/s}" in r.latex


def test_importer_helpers():
    tex = r"""\ifthenelse{\equal{\V}{A}}{\newcommand{\Xa}{1}}{\ifthenelse{\equal{\V}{B}}{\newcommand{\Xa}{2}}{\newcommand{\Xa}{3}}}"""
    assert parse_commands(expand_version(tex, "B")) == {"Xa": "2"}
    assert parse_commands(expand_version(tex, "C")) == {"Xa": "3"}
    assert short_names(["mhsqSixEm", "mhsqSixK"]) == {"mhsqSixEm": "Em", "mhsqSixK": "K"}
    v, _ = infer_variable("m", {"A": "120", "B": "150", "C": "100"}, "m")
    assert v.type == "integer" and v.min <= 100 and v.max >= 150 and v.step == 10


def test_choice_shuffle_follows_answer_and_pins_last():
    from examgen.generate import _choice_shuffle
    qq = q({"type": "conceptuel", "choices": ["a", "b", "c", "d", "aucune"], "answer": "B", "pin_last": 1})
    orders = set()
    for seed in range(30):
        order, ans = _choice_shuffle(qq, random.Random(seed), True)
        assert order[-1] == 4
        assert qq.choices[order[ord(ans) - 65]] == "b"
        orders.add(tuple(order))
    assert len(orders) > 5
