# PyInstaller spec for the Windows desktop app.  Run from app/:  pyinstaller packaging/examgen.spec
# Produces dist/ExamGen/ExamGen.exe ; the build script then adds tinytex/ and seed/ next to it.
import os
from PyInstaller.utils.hooks import collect_submodules

backend = os.path.join(SPECPATH, "..", "backend")
hidden = collect_submodules("uvicorn") + ["examgen.api", "sympy", "multipart", "webview"]
datas = [
    (os.path.join(backend, "examgen", "templates"), os.path.join("examgen", "templates")),
    (os.path.join(backend, "examgen", "static"), os.path.join("examgen", "static")),
]

a = Analysis([os.path.join(backend, "examgen", "desktop.py")], pathex=[backend], hiddenimports=hidden, datas=datas,
             excludes=["tkinter", "matplotlib", "numpy", "scipy", "PIL", "pandas", "IPython", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ExamGen", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="ExamGen")
