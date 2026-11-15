#!/usr/bin/env bash
# Installazione da zero: venv, dipendenze, pesi.
#
#   ./install.sh              base + peso neurale (31 MB)
#   ./install.sh --models     anche Whisper / VLM / volti / DINOv2 (~4 GB, altrimenti al primo run)
set -euo pipefail
cd "$(dirname "$0")"

command -v ffmpeg >/dev/null || { echo "manca ffmpeg → brew install ffmpeg"; exit 1; }

PY="${PYTHON:-python3}"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install -e '.[all]'
.venv/bin/scene-detector-setup "$@"

echo
echo "Fatto. Attiva l'ambiente e lancia:"
echo "  source .venv/bin/activate"
echo "  scene-detector FILM.mp4 --all -o catalogo/"
