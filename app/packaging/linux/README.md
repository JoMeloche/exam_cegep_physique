# Linux desktop app

Two self-contained packages, each with the app, its window (Qt WebEngine), TinyTeX and the starter question bank:

- `ExamGen-x86_64.AppImage`: runs on most distributions without installing anything.
  `chmod +x ExamGen-x86_64.AppImage && ./ExamGen-x86_64.AppImage`
- `examgen_<version>_amd64.deb`: for Debian/Ubuntu/Mint. `sudo apt install ./examgen_*_amd64.deb`, then
  launch "ExamGen" from the menu or run `examgen`.

The library lives in `~/exam_app` (set `EXAM_APP_HOME` to change it) and is filled with the starter bank on first start.

## Building

GitHub Actions builds both on every pull request touching `app/` and on `v*` tags (attached to the release),
see `.github/workflows/build-linux.yml`. To build locally (Python 3.11+, Node 20+, curl, perl):

```sh
bash app/packaging/linux/build_linux.sh          # -> app/packaging/linux/dist/
xvfb-run bash app/packaging/linux/smoke_test.sh app/packaging/linux/dist/ExamGen-x86_64.AppImage
```

Notes: the build runs on Ubuntu 22.04 so the AppImage also works on older systems (glibc 2.35+). The Chromium
sandbox of the window is turned off because several distributions block the user namespaces it needs; the
window only shows the app served on 127.0.0.1. If the AppImage complains about FUSE, run it with
`--appimage-extract-and-run` or install `libfuse2`.
