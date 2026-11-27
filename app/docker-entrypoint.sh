#!/bin/sh
set -e
mkdir -p "$EXAM_APP_HOME"
# First start: copy the starter question bank (never overwrites existing files).
if [ -d /app/seed/questions ] && [ -z "$(ls -A "$EXAM_APP_HOME/questions" 2>/dev/null)" ]; then
  echo "Première utilisation : copie de la banque de questions dans $EXAM_APP_HOME"
  cp -rn /app/seed/. "$EXAM_APP_HOME/"
fi
# Run the app as an unprivileged user. Libraries created by older versions (as root) are handed over once.
if [ "$(id -u)" = "0" ] && id examgen >/dev/null 2>&1; then
  if [ "$(stat -c %U "$EXAM_APP_HOME")" != "examgen" ] || [ -n "$(find "$EXAM_APP_HOME" -maxdepth 3 ! -user examgen -print -quit)" ]; then
    chown -R examgen:examgen "$EXAM_APP_HOME"
  fi
  HOME="$EXAM_APP_HOME" exec setpriv --reuid=examgen --regid=examgen --init-groups "$@"
fi
exec "$@"
