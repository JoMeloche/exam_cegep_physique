import os
import sys

from examgen import opener


def _frozen(monkeypatch, tmp_path):
    bundle = tmp_path / "mount" / "usr" / "lib" / "examgen" / "_internal"
    bundle.mkdir(parents=True)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(bundle.parent / "ExamGen"))
    monkeypatch.setenv("APPDIR", str(tmp_path / "mount"))
    return str(bundle)


def test_bundle_libraries_are_not_passed_to_system_programs(monkeypatch, tmp_path):
    bundle = _frozen(monkeypatch, tmp_path)
    env = opener.external_env({
        "LD_LIBRARY_PATH": bundle, "QT_PLUGIN_PATH": f"{bundle}/PyQt6/Qt6/plugins", "QT_API": "pyqt6",
        "PYWEBVIEW_GUI": "qt", "QTWEBENGINE_DISABLE_SANDBOX": "1", "_PYI_APPLICATION_HOME_DIR": bundle,
        "PATH": f"{bundle}/../tinytex/bin/x86_64-linux{os.pathsep}/usr/bin", "HOME": "/home/jo",
        "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "KDE",
    })
    assert env == {"PATH": "/usr/bin", "HOME": "/home/jo", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "KDE"}


def test_user_values_are_restored_or_kept(monkeypatch, tmp_path):
    bundle = _frozen(monkeypatch, tmp_path)
    env = opener.external_env({"LD_LIBRARY_PATH": bundle, "LD_LIBRARY_PATH_ORIG": "/opt/cuda/lib64",
                               "QT_PLUGIN_PATH": "/home/jo/qtplugins"})
    assert env == {"LD_LIBRARY_PATH": "/opt/cuda/lib64", "QT_PLUGIN_PATH": "/home/jo/qtplugins"}


def test_not_frozen_keeps_environment():
    env = {"LD_LIBRARY_PATH": "/usr/local/lib", "PATH": "/usr/bin", "HOME": "/h"}
    assert opener.external_env(env) == env


def test_xdg_open_gets_clean_environment(monkeypatch, tmp_path):
    bundle = _frozen(monkeypatch, tmp_path)
    monkeypatch.setenv("LD_LIBRARY_PATH", bundle)
    monkeypatch.setattr(opener.platform, "system", lambda: "Linux")
    calls = []
    monkeypatch.setattr(opener.subprocess, "Popen", lambda cmd, **kw: calls.append((cmd, kw)))
    opener.install_webbrowser_hook()
    try:
        import webbrowser
        assert webbrowser.open("http://127.0.0.1:1234/api/previews/x.pdf")
    finally:
        import importlib
        importlib.reload(sys.modules["webbrowser"])
    (cmd, kw), = calls
    assert cmd == ["xdg-open", "http://127.0.0.1:1234/api/previews/x.pdf"]
    assert "LD_LIBRARY_PATH" not in kw["env"]
