# Question format spec (v1)

Owner: app thread. The engine in `exam_app/app/backend/examgen/` implements exactly this.
Anything not listed here is ignored by the engine (safe to add notes).

## Layout

```
<library root>/                      ~/exam_app on Jo's machine, /mnt/project-files/exam_app/ here (app code lives in its app/ subfolder)
  questions/<course>/<topic>/<name>.tex        question body
  questions/<course>/<topic>/<name>.yaml       metadata
  questions/<course>/<topic>/<name>.sol.tex    manual solution (only when solution.mode = manual)
  figures/<file>.png                           shared figures
  exams/<course>/examen_<N>.yaml               exam structure (topics, counts, points)
  config.yaml                                  professors, courses, school
```

- `<course>`: course code, e.g. `203-SN3-RE`.
- `<topic>`: ASCII folder name, no accents, no spaces (`MHS`, `Onde_stationnaire`, `Intensite`, `Doppler`, ...).
  A human label can be given in `exams/...yaml` or `config.yaml`.
- `<name>`: ASCII, `[A-Za-z0-9_-]`. The question id is `<course>/<topic>/<name>`.

## `<name>.tex` (question body)

- Body only: no `\documentclass`, no `\begin{document}`, **no leading `\subsection{}`**.
  The engine writes the heading itself (with the points box for development questions, numbered
  for conceptual ones). If a file starts with `\subsection{}` the engine strips it, so old files still work.
- Values: `\v{name}` is replaced by the drawn value as a plain number with a dot decimal
  (`0.25`, `1.2e-3` is never produced; small numbers are written in full). Use it inside
  `\qty{\v{m}}{g}`, `\num{\v{k}}`, `$\v{x}$`, `\fpeval{...}`.
- `\vsi{name}` gives the same value converted to SI (value × `si`), handy in `\fpeval`.
- Substitution happens before LaTeX runs, so `\v` never reaches the compiler. Only declared
  variable names are replaced; an unknown `\v{x}` is a validation error.
- Figures: `\includegraphics[...]{Figures/<file>.png}` and list the file under `figures:`.
- Packages available: the preamble of Jo's main.tex (exam class, babel french, amsmath, amssymb,
  geometry, enumitem, tikz with patterns/decorations.pathmorphing/arrows.meta, ifthen, xfp,
  siunitx with locale=FR, graphicx). Sub-questions: `\begin{enumerate}[label=\alph*)]`.
- Conceptual answer lines (Réponse / Justification + `\rule`s + `\vfill`) stay in the body.

## `<name>.yaml` (metadata)

```yaml
title: Masse-ressort sachant E, m, k     # required
type: developpement                     # required: developpement | conceptuel
points: 20                              # required (conceptual usually 4)
time_min: 15                            # required, estimated minutes
difficulty: 3                           # required, 1 (easy) to 5 (hard)
figures: []                             # files in figures/
tags: []                                # optional free tags
variables:                              # optional; key = name used in \v{name}
  Em: {type: decimal, min: 0.10, max: 0.40, step: 0.05, unit: J, label: Énergie mécanique}
  m:  {type: integer, min: 80, max: 200, step: 10, unit: g, si: 0.001, label: Masse du bloc}
  k:  {type: integer, min: 20, max: 60, step: 5, unit: N/m, label: Constante de rappel}
  v:  {type: decimal, min: 0.5, max: 2.0, step: 0.1, unit: m/s, label: Vitesse}
constraints:                            # optional; all must be true, evaluated on SI values
  - v < 0.9*sqrt(2*Em/m)
solution:
  mode: manual                          # manual | auto | answers_only | none
  file: masse_ressort_E.sol.tex         # manual only; default <name>.sol.tex
  parts:                                # auto / answers_only (also allowed with manual, for the answer key)
    a: {find: A, equation: "Em = k*A**2/2", unit: m, label: Amplitude}
    b: {find: vmax, equation: "Em = m*vmax**2/2", unit: m/s}
    c: {find: x, equation: "Em = m*v**2/2 + k*x**2/2", unit: m, root: positive}
# conceptual only:
answer: C                               # correct letter
explanation: "La période ne dépend pas de l'amplitude."   # optional, LaTeX allowed
choices:                                # optional: if given, the engine renders the A) B) C) list
  - Une fois                            # at the \choices marker in the .tex and may shuffle it;
  - Deux fois                           # the first-listed order is the one `answer` refers to
pin_last: 1                             # optional: keep the last N choices in place when shuffling
                                        # (e.g. "Aucune de ces réponses", "Cela ne se produit jamais")
history: []                             # ignored; usage is tracked in <library>/usage.json
```

### Variable types

| type      | fields                                   | drawn value |
|-----------|------------------------------------------|-------------|
| `integer` | `min`, `max`, `step` (default 1)         | min + k·step |
| `decimal` | `min`, `max`, and `step` or `decimals`   | on the step grid, or rounded to `decimals` |
| `sigfig`  | `min`, `max`, `sigfigs` (default 3)      | uniform, rounded to n significant figures |
| `choice`  | `values: [340, 343]`                     | one of the numbers |
| `text`    | `values: ["4.2 \\sin(1.35 t)", ...]`     | one of the LaTeX strings (not usable in math) |

Common optional fields: `unit` (LaTeX/siunitx unit as printed), `label` (French, used in the
"Variables connues" step), `si` (factor to SI, number; e.g. `0.001` for g→kg, `0.01` for cm→m;
the string form `"0.001 kg"` is also accepted), `symbol` (LaTeX symbol for auto solutions,
default the name, e.g. `symbol: "E_m"`).

### Expressions (constraints, equations, answers_only `expr`)

Python/SymPy syntax over variable names (SI values): `+ - * / **`, `sqrt sin cos tan asin acos
atan exp log log10 abs min max pi`, plus constants `g = 9.81`, `c = 3e8`, `h = 6.626e-34`,
`e = 1.602e-19`, `k_B = 1.381e-23`, `sigma = 5.67e-8`, `I0 = 1e-12` (only when no variable
of the same name exists). Angles are radians in expressions; use `deg(x)` / `rad(x)` to convert.
Earlier `find` results (e.g. `A`, `vmax`) can be used in later parts.

`answers_only` parts use `{expr: "sqrt(2*Em/k)", unit: m}` instead of `find` + `equation`.

## `<name>.sol.tex` (manual solution)

Same rules as the body (`\v{}`, `\vsi{}`, `\fpeval`). Jo's five-step layout per part:
Variables connues et recherchées, Équations pertinentes, Isolation de la variable,
Résolution numérique, Réponse. No leading heading; the engine places it right after the question
in the solution PDF.

## `exams/<course>/examen_<N>.yaml`

```yaml
course: 203-SN3-RE
number: 1
duration_min: 120
sections:
  - title: Questions à développement
    type: developpement
    slots:
      - {topic: MHS, count: 1, points: 20}
      - {topic: Onde_resonnante, count: 1, points: 20}
  - title: Questions conceptuelles
    type: conceptuel
    points: 20                      # section total, shown in the heading
    slots:
      - {topics: [Onde_progressive, MHS, Onde_stationnaire, Doppler, Puissance], count: 5}
```

## Validation

`python -m examgen validate <library>` checks every question: required fields, every `\v{}`
declared, ranges valid, constraints satisfiable, and compiles each question with 3 random draws.

## Rendering notes

- siunitx is set with `group-digits = none`: 10000 prints as 10000 (no thin spaces).
- Choices are shuffled per version by default (Generate screen switch "Mélanger"); the answer key
  in the solution PDF follows the shuffle.
