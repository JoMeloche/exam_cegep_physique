"""Shared test setup: a throwaway copy of the repository's question bank."""
import os
import shutil
from pathlib import Path

# The repository root holds the starter library (questions/, figures/, exams/, config.yaml).
# Set EXAMGEN_TEST_LIB to test against another library folder.
SRC = Path(os.environ.get("EXAMGEN_TEST_LIB", Path(__file__).resolve().parents[3]))
LIBRARY_PARTS = ("questions", "figures", "exams", "config.yaml")


def copy_library(dst: Path) -> Path:
    dst.mkdir(parents=True, exist_ok=True)
    for part in LIBRARY_PARTS:
        p = SRC / part
        if p.is_dir():
            shutil.copytree(p, dst / part)
        elif p.is_file():
            shutil.copy2(p, dst / part)
    return dst
