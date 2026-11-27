# PyInstaller spec for the macOS desktop app.  Run from app/:  pyinstaller packaging/examgen-macos.spec
# Produces dist/ExamGen.app ; build_macos.sh then adds TinyTeX and the starter bank inside it.
# The bundle targets the architecture of the Python running PyInstaller (arm64 or x86_64).
import os
from PyInstaller.utils.hooks import collect_submodules

backend = os.path.join(SPECPATH, "..", "backend")
version = os.environ.get("EXAMGEN_VERSION", "0.1.0")
hidden = collect_submodules("uvicorn") + collect_submodules("webview.platforms") + [
    "examgen.api", "sympy", "multipart", "webview"]
datas = [
    (os.path.join(backend, "examgen", "templates"), os.path.join("examgen", "templates")),
    (os.path.join(backend, "examgen", "static"), os.path.join("examgen", "static")),
]
icon = os.path.join(SPECPATH, "build", "ExamGen.icns")

a = Analysis([os.path.join(backend, "examgen", "desktop.py")], pathex=[backend], hiddenimports=hidden, datas=datas,
             excludes=["tkinter", "matplotlib", "numpy", "scipy", "PIL", "pandas", "IPython", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ExamGen", console=False, argv_emulation=False)
coll = COLLECT(exe, a.binaries, a.datas, name="ExamGen")
app = BUNDLE(
    coll,
    name="ExamGen.app",
    icon=icon if os.path.exists(icon) else None,
    bundle_identifier="ca.cegep.examgen",
    version=version,
    info_plist={
        "CFBundleDisplayName": "Générateur d'examens",
        "CFBundleName": "ExamGen",
        "CFBundleShortVersionString": version,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.education",
    },
)
