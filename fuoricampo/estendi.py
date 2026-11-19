"""Allunga i segmenti fino a dove la verifica regge.

Trentacinque minuti di film stanno **dentro** shot già agganciati, in porzioni che il voting
non ha preso: una corsa si interrompe appena la somiglianza scende sotto soglia per qualche
campione, anche se la ripresa nel girato continua. Cercarli da capo è inutile — il segmento
accanto dice già dove guardare, perché l'offset lì è noto.

Si prova ad allungare di `PASSO_S` per volta, a offset costante, e si accetta finché il
controllo a piena risoluzione supera la soglia dei casuali. Non è l'impronta a decidere
l'estensione: è la stessa verifica che ha validato i segmenti.

Il limite è il confine dello shot del film: oltre c'è un'altra inquadratura, e coprirla è un
altro problema.

    .venv/bin/python fuoricampo/estendi.py [--applica]
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np

from controllo import RIS, frame, meglio, FIN, PASSO
from impronta import CROP
from timeline import GIRATO, MANIFEST, QUI, annota_passo, copertura
from verifica import FILM

# NON la soglia dei casuali (0,648): estendere è un problema diverso dal riconoscere.
# Appena fuori da un segmento la verifica dà comunque 0,674 di mediana — dentro una ripresa
# continua i fotogrammi vicini si somigliano tutti — quindi con 0,648 l'estensione non si
# ferma mai e la copertura gonfia oltre la durata del film. 0,76 sta in mezzo fra il 0,835
# misurato dentro i segmenti e il 0,674 misurato quindici secondi oltre il bordo.
SOGLIA = 0.76
PASSO_S = 4.0       # quanto si prova ad allungare per volta
MAX_PASSI = 12      # al più 48 s per lato


def regge(tf: float, tg: float, parte: int) -> bool:
    nome = f"Fuori campo di Anna - {parte}"
    a = frame(FILM, tf, CROP["Anna"], 1)
    bs = frame(GIRATO / f"{nome}.mp4", tg - FIN / 2, CROP[nome], int(FIN * PASSO))
    if not len(a) or not len(bs):
        return False
    return meglio(a[0], bs)[0] > SOGLIA


def bordi_shot(shots, t: float) -> tuple[float, float]:
    for sh in shots:
        if sh["start_time"] <= t <= sh["end_time"]:
            return sh["start_time"], sh["end_time"]
    return t, t


def allunga(s: dict, shots) -> dict:
    s = dict(s)
    off = s["girato_start"] - s["film_start"]
    _, fine_shot = bordi_shot(shots, s["film_end"] - 0.1)
    inizio_shot, _ = bordi_shot(shots, s["film_start"] + 0.1)

    for _ in range(MAX_PASSI):                       # in avanti
        nuovo = min(s["film_end"] + PASSO_S, fine_shot)
        if nuovo <= s["film_end"] + 0.5:
            break
        if not regge((s["film_end"] + nuovo) / 2, (s["film_end"] + nuovo) / 2 + off, s["parte"]):
            break
        s["film_end"], s["girato_end"] = nuovo, nuovo + off
    for _ in range(MAX_PASSI):                       # all'indietro
        nuovo = max(s["film_start"] - PASSO_S, inizio_shot)
        if nuovo >= s["film_start"] - 0.5 or nuovo + off < 0:
            break
        if not regge((nuovo + s["film_start"]) / 2, (nuovo + s["film_start"]) / 2 + off, s["parte"]):
            break
        s["film_start"], s["girato_start"] = nuovo, nuovo + off
    s["durata"] = s["film_end"] - s["film_start"]
    return s


if __name__ == "__main__":
    segs = json.loads((QUI / "segmenti-video.json").read_text())
    shots = json.loads(MANIFEST.read_text())["shots"]
    prima = sum(s["durata"] for s in segs)
    t0 = time.time()
    nuovi = []
    for i, s in enumerate(segs, 1):
        nuovi.append(allunga(s, shots))
        if i % 40 == 0:
            print(f"  {i}/{len(segs)} · {(time.time()-t0)/i:.1f} s/segmento", flush=True)
    cresciuti = sum(1 for a, b in zip(segs, nuovi) if b["durata"] > a["durata"] + 0.5)
    chiavi = lambda l: ((x["film_start"], x["film_end"]) for x in l)
    cp, cd = copertura(chiavi(segs)), copertura(chiavi(nuovi))
    print(f"\n{cresciuti}/{len(segs)} segmenti allungati")
    print(f"copertura del film: {cp/60:.1f} -> {cd/60:.1f} min "
          f"({cp/12829:.0%} -> {cd/12829:.0%})   [+{(cd-cp)/60:.1f} min]")
    print(f"somma delle durate: {prima/60:.1f} -> {sum(s['durata'] for s in nuovi)/60:.1f} min "
          f"(la differenza è sovrapposizione fra segmenti vicini)")
    if "--applica" in sys.argv:
        (QUI / "segmenti-video.json").write_text(json.dumps(nuovi, indent=1))
        annota_passo("estendi", nuovi)
        print("scritto. Rilancia controllo.py, poi rigenera le pagine.")
