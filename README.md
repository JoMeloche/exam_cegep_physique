# Générateur d'examens de physique (Cégep)

Application that builds exams automatically from a LaTeX question bank: choose the professor,
course, exam number, date and duration, and get several versions with fresh values plus a
solution PDF for each (`203-SN3-RE_Examen_1_A26_v1.pdf`, `..._v1_solution.pdf`).

| Folder | Contents |
|---|---|
| `app/` | The application: Python engine + API (`app/backend`), React UI (`app/frontend`), Docker and Windows packaging. See [app/README.md](app/README.md). |
| `questions/<course>/<topic>/` | The question bank: `name.tex` (statement), `name.yaml` (variables, time, difficulty, solution), `name.sol.tex` (LaTeX solution). |
| `figures/` | Images used by questions. |
| `exams/<course>/examen_<N>.yaml` | Structure of each exam (topics, number of questions, points). |
| `config.yaml` | School, professors, courses, LaTeX settings. |
| `templates/` | Optional overrides of the cover page and preamble. |
| `docs/question_format.md` | The question file format. |
| `legacy/` | The original hand-made SN3 Examen 1 folder the bank was imported from. |

This repository is also a ready-to-use library: point the app at it with `EXAM_APP_HOME=<this folder>`,
or copy `questions/`, `figures/`, `exams/` and `config.yaml` into `~/exam_app`.

Quick start (web app): `cd app && docker compose up -d --build`, then open http://localhost:8765.
