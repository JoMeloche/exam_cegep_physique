"""Open files, folders and links with the user's own apps (desktop app only).

The packaged app (PyInstaller, and on Linux the AppImage) points the dynamic loader at its bundled
libraries through LD_LIBRARY_PATH and adds Qt/pywebview variables to the environment. A system program
started with that environment (xdg-open, then kde-open, a PDF reader or a browser) loads our Qt instead of
the system one and crashes, e.g. ``kde-open: .../libQt6Core.so.6: version `Qt_6.11_PRIVATE_API' not found``.
Every external program is therefore started with the environment the user's session had before ours.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import webbrowser

# Set by our launchers (examgen_linux.py etc.) for the app's own window.
_LAUNCHER_VARS = ("QT_API", "PYWEBVIEW_GUI", "QTWEBENGINE_DISABLE_SANDBOX", "QTWEBENGINE_CHROMIUM_FLAGS",
                  "EXAMGEN_DESKTOP")
# Set by the PyInstaller/Qt runtime hooks; dropped only when they point inside our bundle, so a value
# the user set themselves is kept.
_BUNDLE_VARS = (
    "QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QTWEBENGINEPROCESS_PATH", "QTWEBENGINE_RESOURCES_PATH", "QTWEBENGINE_LOCALES_PATH",
    "PYTHONHOME", "PYTHONPATH", "TCL_LIBRARY", "TK_LIBRARY", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "GIO_MODULE_DIR", "GDK_PIXBUF_MODULE_FILE", "GTK_PATH", "GTK_EXE_PREFIX", "GTK_DATA_PREFIX",
    "FONTCONFIG_FILE", "FONTCONFIG_PATH", "XDG_DATA_DIRS",
)
# PyInstaller saves the original value of these as NAME_ORIG before pointing them at the bundle.
_LOADER_PATHS = ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH", "LIBPATH")


def _bundle_dirs() -> list[str]:
    dirs = []
    for d in (getattr(sys, "_MEIPASS", None), os.environ.get("APPDIR")):
        if d:
            dirs.append(os.path.realpath(d))
    if getattr(sys, "frozen", False):
        dirs.append(os.path.realpath(os.path.dirname(sys.executable)))
    return dirs


def _inside(path: str, dirs: list[str]) -> bool:
    p = os.path.realpath(path) if path else ""
    return any(p == d or p.startswith(d + os.sep) for d in dirs)


def external_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """The environment to give a program that is not part of the app."""
    env = dict(os.environ if env is None else env)
    bundle = _bundle_dirs()
    for name in _LOADER_PATHS:
        orig = env.pop(name + "_ORIG", None)
        if orig is not None:
            env[name] = orig
        elif name in env:
            kept = [p for p in env[name].split(os.pathsep) if p and not _inside(p, bundle)]
            if kept:
                env[name] = os.pathsep.join(kept)
            else:
                del env[name]
        if not env.get(name):
            env.pop(name, None)
    for name in _LAUNCHER_VARS:
        env.pop(name, None)
    for name in _BUNDLE_VARS:
        if name in env and bundle:
            kept = [p for p in env[name].split(os.pathsep) if p and not _inside(p, bundle)]
            if kept:
                env[name] = os.pathsep.join(kept)
            else:
                del env[name]
    for name in [k for k in env if k.startswith("_PYI") or k == "_MEIPASS2"]:
        env.pop(name, None)
    if bundle and env.get("PATH"):  # keep the user's PATH, drop our bundle (TinyTeX, etc.)
        env["PATH"] = os.pathsep.join(p for p in env["PATH"].split(os.pathsep) if p and not _inside(p, bundle))
    return env


def open_with_os(target: str) -> None:
    """Open a file, a folder or a URL with the default app of the user's system."""
    system = platform.system()
    if system == "Windows":
        os.startfile(target)  # type: ignore[attr-defined]  # noqa: S606
        return
    cmd = ["open", target] if system == "Darwin" else ["xdg-open", target]
    subprocess.Popen(cmd, env=external_env(), stdin=subprocess.DEVNULL,  # noqa: S603
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def install_webbrowser_hook() -> None:
    """pywebview opens target=_blank links with ``webbrowser.open``, which on Linux runs kde-open,
    gio, firefox... with our environment. Route those links through :func:`open_with_os` instead."""
    if platform.system() == "Windows":
        return  # os.startfile does not pass our environment to the browser

    def _open(url: str, new: int = 0, autoraise: bool = True) -> bool:  # noqa: ARG001
        try:
            open_with_os(url)
            return True
        except OSError:
            return False

    webbrowser.open = _open  # type: ignore[assignment]
    webbrowser.open_new = lambda url: _open(url, 1)  # type: ignore[assignment]
    webbrowser.open_new_tab = lambda url: _open(url, 2)  # type: ignore[assignment]
