"""I pezzi scoperti **dentro** shot già agganciati: cercarli senza dare per buono l'offset.

`estendi.py` allunga un segmento tenendo fermo il suo offset, e si ferma dove la verifica non
regge più. Ma dentro uno stesso shot del film il montaggio può aver ricucito pezzi presi da
**punti diversi** del girato: lì l'offset del vicino è la risposta sbagliata, e allungare non
serve — bisogna cercare.

Qui ogni buco viene ripreso dai candidati già calcolati (`candidati.npz`), senza vincolo di
offset, e il risultato passa da `controllo.py` come qualunque altro segmento: entra solo se
supera il massimo dei quaranta accoppiamenti casuali.

    .venv/bin/python fuoricampo/buchi.py [--applica]
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np

from controllo import controlla
from impronta import FPS
from match import MIN_CONTRASTO, contrasto_film
from timeline import MANIFEST, QUI, annota_passo, copertura, sovrapposizione

SOGLIA_VERA = 0.648
MIN_BUCO = 2.0        # sotto i due secondi non vale la pena
MIN_CORR = 0.70       # il candidato deve almeno somigliare, poi decide il controllo


def trova_buchi(shots, segs):
    """(shot, inizio, fine) delle porzioni scoperte dentro shot che un segmento tocca."""
    fuori = []
    for sh in shots:
        vicini = [s for s in segs
                  if sovrapposizione(sh["start_time"], sh["end_time"],
                                     s["film_start"], s["film_end"]) > 0]
        if not vicini:
            continue
        coperti = sorted((max(sh["start_time"], s["film_start"]),
                          min(sh["end_time"], s["film_end"])) for s in vicini)
        t = sh["start_time"]
        for a, b in coperti:
            if a - t > MIN_BUCO:
                fuori.append((sh, t, a))
            t = max(t, b)
        if sh["end_time"] - t > MIN_BUCO:
            fuori.append((sh, t, sh["end_time"]))
    return fuori


def candidato(a: float, b: float, d, contrasto) -> dict | None:
    """Il miglior aggancio per il buco [a, b], preso dai candidati già calcolati."""
    idx, val, file_di, inizi = d["idx"], d["val"], d["file_di"], d["inizi"]
    i0, i1 = int(a * FPS), min(int(b * FPS), len(val))
    if i1 - i0 < 2:
        return None
    # vale anche qui la regola del matcher: un pezzo di film al buio non è verificabile, e
    # accoppia con qualunque cosa. Senza questo controllo rientrava dalla finestra il tipo di
    # falso che `MIN_CONTRASTO` aveva già escluso altrove.
    if float(np.median(contrasto[i0:i1])) < MIN_CONTRASTO:
        return None
    finestra = val[i0:i1, 0]
    if finestra.max() < MIN_CORR:
        return None
    k = i0 + int(np.argmax(finestra))
    g = int(idx[k, 0])
    parte = int(file_di[g])
    base = int(inizi[parte - 1])
    off = (g - base) / FPS - k / FPS         # l'offset che il candidato propone
    if (a + off) < 0:
        return None
    return {"film_start": a, "film_end": b, "parte": parte,
            "girato_start": a + off, "girato_end": b + off,
            "durata": b - a, "score": round(float(finestra.max()), 3),
            "n": i1 - i0}


if __name__ == "__main__":
    d = np.load(QUI / "candidati.npz")
    segs = json.loads((QUI / "segmenti-video.json").read_text())
    shots = json.loads(MANIFEST.read_text())["shots"]
    buchi = trova_buchi(shots, segs)
    print(f"buchi dentro shot agganciati: {len(buchi)} · "
          f"{sum(b - a for _, a, b in buchi)/60:.1f} min")

    contrasto = contrasto_film(np.load(QUI / "dati" / "Anna.npy"))
    proposte = [c for c in (candidato(a, b, d, contrasto) for _, a, b in buchi) if c]
    print(f"con un candidato sopra {MIN_CORR}: {len(proposte)}")

    t0 = time.time()
    esiti = []
    for i, c in enumerate(proposte, 1):
        esiti.append(controlla(c))
        if i % 20 == 0:
            print(f"  {i}/{len(proposte)} · {(time.time()-t0)/i:.1f} s/candidato", flush=True)
    buoni = [e for e in esiti if e["controllo"] > SOGLIA_VERA]
    (QUI / "buchi.json").write_text(json.dumps(esiti, indent=1))
    print(f"\nconfermati dal controllo: {len(buoni)}/{len(esiti)} · "
          f"{sum(b['durata'] for b in buoni)/60:.1f} min")

    # quanti sono davvero altrove, cioè pezzi che il montaggio ha preso da un altro punto
    altrove = 0
    for b in buoni:
        vic = [s for s in segs if s["parte"] == b["parte"]
               and sovrapposizione(b["film_start"], b["film_end"],
                                   s["film_start"] - 60, s["film_end"] + 60) > 0]
        if not vic or abs((b["girato_start"] - b["film_start"])
                          - (vic[0]["girato_start"] - vic[0]["film_start"])) > 5.0:
            altrove += 1
    print(f"di cui presi da un punto diverso del girato: {altrove}")

    if "--applica" in sys.argv and buoni:
        campi = ("film_start", "film_end", "parte", "girato_start", "girato_end",
                 "durata", "score", "n")
        uniti = segs + [{k: b[k] for k in campi} for b in buoni]
        uniti.sort(key=lambda x: x["film_start"])
        (QUI / "segmenti-video.json").write_text(json.dumps(uniti, indent=1))
        annota_passo("buchi", uniti)
        ctrl = json.loads((QUI / "controllo.json").read_text()) + buoni
        ctrl.sort(key=lambda x: x["film_start"])
        (QUI / "controllo.json").write_text(json.dumps(ctrl, indent=1))
        prima = copertura((s["film_start"], s["film_end"]) for s in segs)
        dopo = copertura((s["film_start"], s["film_end"]) for s in uniti)
        print(f"\ncopertura: {prima/60:.1f} -> {dopo/60:.1f} min "
              f"({prima/12829:.0%} -> {dopo/12829:.0%})")
