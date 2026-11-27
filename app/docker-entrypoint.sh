#!/bin/sh
set -e
mkdir -p "$EXAM_APP_HOME"
# First start: copy the starter question bank (never overwrites existing files).
if [ -d /app/seed/questions ] && [ -z "$(ls -A "$EXAM_APP_HOME/questions" 2>/dev/null)" ]; then
  echo "Première utilisation : copie de la banque de questions dans $EXAM_APP_HOME"
  cp -rn /app/seed/. "$EXAM_APP_HOME/"
fi
exec "$@"
