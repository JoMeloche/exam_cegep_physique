#!/usr/bin/env python3
"""Compile-check question files.

For every <name>.yaml under the given folders: draw N random value sets that
satisfy the constraints, substitute \\v{var} in <name>.tex and the solution
file, and compile each with pdflatex. Prints one line per question.

Usage: python3 check_questions.py [--n 3] [--keep DIR] folder [folder ...]
"""
import argparse, math, random, re, subprocess, sys, tempfile, pathlib, shutil
import yaml

PREAMBLE = r"""\documentclass[11pt,addpoints]{exam}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}
\usepackage{amsmath,amssymb}
\usepackage[margin=2cm]{geometry}
\usepackage{enumitem}
\usepackage{graphicx}
\usepackage{tikz}
\usetikzlibrary{patterns,decorations.pathmorphing,arrows.meta}
\usepackage{ifthen}
\usepackage{xfp}
\usepackage{siunitx}
\sisetup{locale = FR}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}
\begin{document}
"""
VAR = re.compile(r"\\(v|vsi)\{([A-Za-z][A-Za-z0-9_]*)\}")
SAFE = {k: getattr(math, k) for k in ("sqrt", "sin", "cos", "tan", "asin", "acos",
        "atan", "log", "log10", "exp", "pi", "radians", "degrees")}
SAFE.update(abs=abs, min=min, max=max, round=round, deg=math.degrees, rad=math.radians,
            g=9.81, c=3e8, h=6.626e-34, e=1.602e-19, k_B=1.381e-23, sigma=5.67e-8, I0=1e-12)


def si_factor(spec):
    f = spec.get("si", 1)
    if isinstance(f, str):
        f = float(f.split()[0])
    return f


def draw(spec, rng):
    t = spec.get("type", "decimal")
    if t in ("choice", "text"):
        return rng.choice(spec["values"])
    if t == "sigfig":
        v = rng.uniform(spec["min"], spec["max"])
        n = spec.get("sigfigs", 3)
        return float(f"{v:.{n-1}e}")
    if "decimals" in spec and "step" not in spec:
        return round(rng.uniform(spec["min"], spec["max"]), spec["decimals"])
    lo, hi, step = spec["min"], spec["max"], spec.get("step", 1)
    n = int(round((hi - lo) / step))
    v = lo + step * rng.randint(0, n)
    if t == "integer":
        return int(round(v))
    dec = max(0, -int(math.floor(math.log10(step))) if step < 1 else 0)
    return round(v, dec + 2)


def fmt(v):
    if isinstance(v, str):
        return v
    if isinstance(v, int):
        return str(v)
    s = f"{v:.15f}".rstrip("0").rstrip(".")
    return s


def draw_set(meta, rng, tries=2000):
    vars_ = meta.get("variables") or {}
    cons = meta.get("constraints") or []
    for _ in range(tries):
        vals = {k: draw(s, rng) for k, s in vars_.items()}
        sivals = {k: (v * si_factor(vars_[k]) if not isinstance(v, str) else v) for k, v in vals.items()}
        vals["__si__"] = sivals
        try:
            if all(eval(c, {"__builtins__": {}}, {**SAFE, **sivals}) for c in cons):
                return vals
        except Exception as e:  # noqa
            raise SystemExit(f"constraint error {cons}: {e}")
    raise RuntimeError("no value set satisfies the constraints")


def subst(text, vals, where):
    def rep(m):
        kind, k = m.group(1), m.group(2)
        if k not in vals:
            raise KeyError(f"\\{kind}{{{k}}} in {where} has no variable")
        return fmt(vals["__si__"][k] if kind == "vsi" else vals[k])
    return VAR.sub(rep, text)


def check(yml, n, keep, fig_dirs):
    meta = yaml.safe_load(yml.read_text(encoding="utf-8"))
    qtex = yml.with_suffix(".tex").read_text(encoding="utf-8")
    sol = meta.get("solution") or {}
    soltex = ""
    if sol.get("mode") == "manual":
        sol.setdefault("file", yml.stem + ".sol.tex")
        soltex = (yml.parent / sol["file"]).read_text(encoding="utf-8")
    for need in ("title", "type", "points", "time_min", "difficulty"):
        if need not in meta:
            return f"missing field {need}"
    if meta["type"] == "conceptuel" and "answer" not in meta and not soltex:
        return "conceptual question without answer"
    rng = random.Random(hash(yml.name) & 0xffff)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        for d in fig_dirs:
            if d.exists():
                shutil.copytree(d, tmp / "Figures", dirs_exist_ok=True)
        body = []
        for i in range(n):
            vals = draw_set(meta, rng)
            body.append(r"\section*{Jeu %d}" % (i + 1))
            body.append(r"\subsection{}")
            q = re.sub(r"^\s*\\subsection\{\}", "", qtex)
            if "\\choices" in q:
                if not meta.get("choices"):
                    return "\\choices marker without choices list"
                items = "\n".join("    \\item " + str(c) for c in meta["choices"])
                q = q.replace("\\choices", "\\begin{enumerate}[label=\\Alph*)]\n" + items + "\n\\end{enumerate}")
            elif meta.get("choices"):
                return "choices list but no \\choices marker"
            body.append(subst(q, vals, yml.stem + ".tex"))
            body.append(r"\par\medskip\hrule\medskip")
            if soltex:
                body.append(subst(soltex, vals, sol["file"]))
            body.append(r"\newpage")
        doc = PREAMBLE + "\n".join(body) + "\n\\end{document}\n"
        (tmp / "q.tex").write_text(doc, encoding="utf-8")
        r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "q.tex"],
                           cwd=tmp, capture_output=True, text=True, errors="replace")
        log = (tmp / "q.log").read_text(errors="replace") if (tmp / "q.log").exists() else r.stdout
        if r.returncode != 0:
            err = [l for l in log.splitlines() if l.startswith("!")][:1]
            ctx = log[log.find("!"):log.find("!") + 400] if "!" in log else log[-400:]
            return "FAIL " + (err[0] if err else "") + "\n" + ctx
        bad = [l for l in log.splitlines() if "Undefined control" in l or "Missing" in l]
        if keep:
            keep.mkdir(parents=True, exist_ok=True)
            shutil.copy(tmp / "q.pdf", keep / (yml.stem + ".pdf"))
        return "ok" if not bad else "WARN " + bad[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--keep", type=pathlib.Path)
    ap.add_argument("--figures", type=pathlib.Path, action="append", default=[])
    ap.add_argument("folders", nargs="+", type=pathlib.Path)
    a = ap.parse_args()
    fails = 0
    for f in a.folders:
        for yml in ([f] if f.is_file() else sorted(f.rglob("*.yaml"))):
            try:
                res = check(yml, a.n, a.keep, a.figures)
            except Exception as e:
                res = f"FAIL {type(e).__name__}: {e}"
            if res != "ok":
                fails += 1
            print(f"{yml.relative_to(f.parent)}: {res}")
    print(f"{fails} problem(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
