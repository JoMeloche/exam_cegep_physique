#!/usr/bin/env bash
# Smoke test for the Linux build: start the AppImage with a fresh home, check that it serves
# the API, finds the bundled pdflatex, and exports one exam to PDF.
# Usage: smoke_test.sh path/to/ExamGen-x86_64.AppImage   (needs a DISPLAY, e.g. Xvfb)
set -euo pipefail
IMG="$(readlink -f "$1")"
export HOME="$(mktemp -d)"
export NO_PROXY="127.0.0.1,localhost" no_proxy="127.0.0.1,localhost"
LOG="$HOME/app.log"
setsid "$IMG" --appimage-extract-and-run >"$LOG" 2>&1 &
APP_PID=$!
trap 'kill -- -$APP_PID 2>/dev/null || true' EXIT  # whole process group (app + Qt helpers)

listening_ports() {
  python3 - <<'PY'
for l in open('/proc/net/tcp').readlines()[1:]:
    p = l.split()
    if p[3] == '0A' and p[1].startswith('0100007F'):
        print(int(p[1].split(':')[1], 16))
PY
}
PORT=""
for _ in $(seq 90); do
  for p in $(listening_ports); do
    if curl -sf --max-time 2 "http://127.0.0.1:$p/api/health" -o "$HOME/health.json" 2>/dev/null \
       && grep -q "\"root\":\"$HOME/exam_app\"" "$HOME/health.json"; then PORT=$p; break 2; fi
  done
  sleep 2
done
[ -n "$PORT" ] || { echo "app did not start"; cat "$LOG"; exit 1; }
echo "health: $(cat "$HOME/health.json")"
grep -q '"latex":"/[^"]*tinytex/bin/x86_64-linux/pdflatex"' "$HOME/health.json" \
  || { echo "bundled pdflatex not found"; exit 1; }

course=$(ls "$HOME/exam_app/exams" | head -1)
number=$(ls "$HOME/exam_app/exams/$course" | head -1 | sed 's/[^0-9]//g')
curl -sf -X PUT -H 'content-type: application/json' "http://127.0.0.1:$PORT/api/config" -d '{"school":"Test"}' >/dev/null
echo "exporting $course exam $number"
curl -sS --max-time 600 -X POST -H 'content-type: application/json' "http://127.0.0.1:$PORT/api/exams/export" \
  -d "{\"course\":\"$course\",\"exam_number\":$number,\"date\":\"2026-12-10\",\"professor\":\"Test\",\"duration_min\":120,\"n_versions\":1,\"seed\":1}" \
  | head -c 300; echo
n=$(find "$HOME/exam_app/exports" -name '*.pdf' | wc -l)
[ "$n" -gt 0 ] || { echo "no PDF produced"; tail -50 "$LOG"; exit 1; }
echo "OK: $n PDF(s) exported"
