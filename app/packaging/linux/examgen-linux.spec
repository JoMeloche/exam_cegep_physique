# PyInstaller spec for the Linux desktop app.  Run from app/:  pyinstaller packaging/linux/examgen-linux.spec
# Produces dist/ExamGen/ExamGen ; build_linux.sh then adds tinytex/ and seed/ next to it and wraps it
# into an AppImage and a .deb.
import os
from PyInstaller.utils.hooks import collect_submodules

app_dir = os.path.join(SPECPATH, "..", "..")
backend = os.path.join(app_dir, "backend")
hidden = collect_submodules("uvicorn") + collect_submodules("webview.platforms") + [
    "examgen.api", "examgen.desktop", "sympy", "multipart", "webview", "qtpy",
    "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore", "PyQt6.QtWebChannel", "PyQt6.QtNetwork",
]
datas = [
    (os.path.join(backend, "examgen", "templates"), os.path.join("examgen", "templates")),
    (os.path.join(backend, "examgen", "static"), os.path.join("examgen", "static")),
]

a = Analysis([os.path.join(SPECPATH, "examgen_linux.py")], pathex=[backend], hiddenimports=hidden, datas=datas,
             excludes=["tkinter", "matplotlib", "numpy", "scipy", "PIL", "pandas", "IPython", "pytest",
                       "gi", "PyQt5", "PySide2", "PySide6", "PyQt6.QtQuick3D", "PyQt6.Qt3DCore",
                       "PyQt6.QtMultimedia", "PyQt6.QtBluetooth", "PyQt6.QtSensors", "PyQt6.QtSerialPort"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ExamGen", console=False, strip=False)
coll = COLLECT(exe, a.binaries, a.datas, name="ExamGen")
