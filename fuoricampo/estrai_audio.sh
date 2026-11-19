#!/bin/bash
# Impronte audio di film + 6 parti del girato.
set -e
cd "$(dirname "$0")"
D=audio
../../.venv/bin/python impronta_audio.py "../../Film/Anna.mp4" $D
for i in 1 2 3 4 5 6; do
  ../../.venv/bin/python impronta_audio.py \
    "/Users/pietrobambagioni/Desktop/cartella senza nome/anna film/Fuori campo di Anna - $i.mp4" $D
done
echo FATTO
