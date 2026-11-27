"""Command line: examgen generate | validate | import-folder | serve."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from .library import Library


def _lib(args) -> Library:
    return Library(args.root).ensure() if args.root else Library().ensure()


def cmd_generate(args) -> int:
    from .generate import ExamRequest, export_exam, plan_exam
    lib = _lib(args)
    req = ExamRequest(
        course=args.course, exam_number=args.exam, date=dt.date.fromisoformat(args.date),
        professor=args.professor or lib.config.get("default_professor", ""),
        duration_min=args.duration, n_versions=args.versions, mode=args.mode, seed=args.seed,
    )
    plan = plan_exam(lib, req)
    for w in plan.warnings:
        print("ATTENTION:", w)
    res = export_exam(lib, plan, record_usage=not args.no_record)
    for f in res.files:
        print(f)
    return 0


def cmd_validate(args) -> int:
    from .validate import validate_library
    lib = _lib(args)
    report = validate_library(lib, compile_check=not args.no_compile, draws=args.draws, course=args.course,
                              only=args.only)
    bad = 0
    for qid, errs in report.items():
        if errs:
            bad += 1
            print(f"✗ {qid}")
            for e in errs:
                print(f"    - {e}")
        elif args.verbose:
            print(f"✓ {qid}")
    print(f"{len(report) - bad}/{len(report)} questions valides")
    return 1 if bad else 0


def cmd_import(args) -> int:
    from .importer import import_folder
    lib = _lib(args)
    rep = import_folder(Path(args.folder), lib, course=args.course, overwrite=args.overwrite)
    print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_serve(args) -> int:
    import uvicorn
    import os
    if args.root:
        os.environ["EXAM_APP_HOME"] = args.root
    uvicorn.run("examgen.api:app", host=args.host, port=args.port, reload=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="examgen")
    ap.add_argument("--root", help="dossier de la bibliothèque (défaut ~/exam_app)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="générer un examen")
    g.add_argument("--course", required=True)
    g.add_argument("--exam", type=int, required=True)
    g.add_argument("--date", default=dt.date.today().isoformat())
    g.add_argument("--professor")
    g.add_argument("--duration", type=int, default=120)
    g.add_argument("--versions", type=int, default=3)
    g.add_argument("--mode", choices=["same", "different"], default="same")
    g.add_argument("--seed", type=int)
    g.add_argument("--no-record", action="store_true")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate", help="valider les questions")
    v.add_argument("--course")
    v.add_argument("--only", help="un id de question ou un préfixe cours/thème")
    v.add_argument("--no-compile", action="store_true")
    v.add_argument("--draws", type=int, default=3)
    v.add_argument("-v", "--verbose", action="store_true")
    v.set_defaults(func=cmd_validate)

    i = sub.add_parser("import-folder", help="importer un dossier d'examen LaTeX existant")
    i.add_argument("folder")
    i.add_argument("--course", required=True)
    i.add_argument("--overwrite", action="store_true")
    i.set_defaults(func=cmd_import)

    s = sub.add_parser("serve", help="lancer l'application web")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.set_defaults(func=cmd_serve)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
