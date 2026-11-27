# Générateur d'examens

Automated exam generation from a LaTeX question library: pick professor, course, exam number,
date and duration, get N versions with fresh values and a solution PDF for each, named
`203-SN3-RE_Examen_1_A26_v1.pdf` / `..._v1_solution.pdf`.

```
app/
  backend/            Python package `examgen` (engine, importer, API, desktop launcher), tests/
  frontend/           React + Tailwind UI (built into backend/examgen/static/)
  packaging/          Windows build: PyInstaller spec, TinyTeX package list, Inno Setup script
  Dockerfile          web app image (UI + API + TeX Live)
  docker-compose.yml
  seed/               starter library shipped in the installer and the image (refresh: sh make_seed.sh)
```

The library lives in `~/exam_app` (override with `EXAM_APP_HOME`), format in `../docs/question_format.md`:

```
~/exam_app/questions/<course>/<topic>/<name>.tex|.yaml|.sol.tex
~/exam_app/figures/   exams/<course>/examen_<N>.yaml   config.yaml   usage.json
~/exam_app/exports/<course>/Examen_<N>_<session>/   PDFs + tex/ + record.json
```

## Run it

### Web app in Docker (Jo)
```
cd app
docker compose up -d --build        # then open http://localhost:8765
```
`~/exam_app` is mounted at `/data`; on first start an empty library gets the starter bank.
If Docker Hub rate-limits you: `docker build --build-arg REGISTRY=mirror.gcr.io/library -t examgen .`

### Windows desktop app (colleagues)
On a Windows PC with Python 3.12, Node 20+ and Inno Setup 6:
```
cd app
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```
Output: `packaging\Output\ExamGen-Setup.exe`. Per-user install (no admin), its own window
(Edge WebView2), LaTeX bundled (TinyTeX with the packages in `packaging/tex-packages.txt`),
starter question bank copied to `%USERPROFILE%\exam_app` on first launch.

### From source (development)
```
pip install -e "backend[dev]"
cd frontend && npm ci && npm run build && cp -r dist/. ../backend/examgen/static/ && cd ..
python -m examgen serve                     # http://127.0.0.1:8765
# UI hot reload: (cd frontend && npm run dev)  -> http://localhost:5173, proxies /api
```
Needs a LaTeX install (pdflatex + exam, babel-french, siunitx, xfp, pgf, enumitem, lm).

## Command line
```
python -m examgen generate --course 203-SN3-RE --exam 1 --date 2026-09-28 --versions 3
python -m examgen validate [--only 203-SN3-RE/MHS] [--no-compile] [-v]
python -m examgen import-folder <old exam folder> --course 203-SN3-RE
```

## Tests
```
cd backend && python -m pytest tests
```
