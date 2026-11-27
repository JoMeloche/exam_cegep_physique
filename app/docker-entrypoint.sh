#!/bin/sh
set -e
mkdir -p "$EXAM_APP_HOME"
if [ -d /app/seed/questions ] && [ -z "$(ls -A "$EXAM_APP_HOME/questions" 2>/dev/null)" ]; then
  echo "Bibliothèque vide : copie de la banque de questions de départ dans $EXAM_APP_HOME"
  cp -rn /app/seed/. "$EXAM_APP_HOME/"
fi
exec "$@"
