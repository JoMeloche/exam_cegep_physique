#!/bin/sh
# Refresh app/seed/ (starter library shipped in the Docker image and the Windows installer)
# from the shared library one folder up. Exports and usage history are not copied.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
lib="$here/.."
mkdir -p "$here/seed"
for d in questions figures exams templates; do
  [ -d "$lib/$d" ] && cp -r "$lib/$d" "$here/seed/"
done
[ -f "$lib/config.yaml" ] && cp "$lib/config.yaml" "$here/seed/"
echo "seed updated: $(find "$here/seed/questions" -name '*.yaml' | wc -l) questions"
