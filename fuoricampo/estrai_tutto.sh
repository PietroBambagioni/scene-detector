#!/bin/bash
# Impronte di film + 6 parti del girato, in sequenza (ffmpeg satura già i core da solo).
set -e
cd "$(dirname "$0")/../.."
D=fuoricampo/dati
.venv/bin/python fuoricampo/impronta.py "Film/Anna.mp4" $D
for i in 1 2 3 4 5 6; do
  .venv/bin/python fuoricampo/impronta.py \
    "/Users/pietrobambagioni/Desktop/cartella senza nome/anna film/Fuori campo di Anna - $i.mp4" $D
done
echo FATTO
