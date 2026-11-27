"""Linux entry point for the packaged desktop app (AppImage / .deb).

Sets up the Qt WebEngine backend of pywebview, then runs the shared launcher in examgen.desktop.
"""
import os
import sys

os.environ.setdefault("PYWEBVIEW_GUI", "qt")
os.environ.setdefault("QT_API", "pyqt6")
# Chromium's sandbox needs unprivileged user namespaces, which several distributions
# (Ubuntu 24.04+, some Debian setups) block for apps outside /usr. The window only shows
# the local app served on 127.0.0.1, so running it without that sandbox is safe.
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
if os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from examgen.desktop import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
