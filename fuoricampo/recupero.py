"""Gli shot rimasti senza aggancio, ricercati a soglie basse e verificati uno per uno.

Le soglie del run principale sono scelte per tenere basso il rumore su tutto il film. Sugli
shot che non hanno trovato niente si può abbassare la guardia, perché ogni candidato viene
poi ripreso a piena risoluzione da `controllo.py`: quello che passa **il massimo raggiunto da
quaranta accoppiamenti casuali** entra, il resto no. Non è la soglia dell'impronta a decidere,
è la verifica.

    .venv/bin/python fuoricampo/recupero.py
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np

import match
from controllo import controlla
from impronta import FPS
from timeline import MANIFEST, QUI, annota_passo, sovrapposizione

SOGLIA_VERA = 0.648      # il massimo dei controlli casuali: sotto, non si distingue dal caso
BASSE = dict(TH_FRAME=0.60, TH_SEG=0.68, MIN_LEN=6)


def scoperti(shots, segs):
    """Gli shot che nessun segmento copre in modo apprezzabile (le regole di `per_shot`)."""
    fuori = []
    for sh in shots:
        durata = max(sh["end_time"] - sh["start_time"], 1e-6)
        coperto = sum(sovrapposizione(sh["start_time"], sh["end_time"],
                                      s["film_start"], s["film_end"]) for s in segs)
        if coperto < 1.0 or coperto / durata < 0.10:
            fuori.append(sh)
    return fuori


if __name__ == "__main__":
    d = np.load(QUI / "candidati.npz")
    segs = json.loads((QUI / "segmenti-video.json").read_text())
    shots = json.loads(MANIFEST.read_text())["shots"]
    buchi = scoperti(shots, segs)
    print(f"shot senza aggancio: {len(buchi)} su {len(shots)}")

    prima = (match.TH_FRAME, match.TH_SEG, match.MIN_LEN)
    match.TH_FRAME, match.TH_SEG, match.MIN_LEN = BASSE.values()
    larghi = match.segmenti(d["idx"], d["val"], d["file_di"], d["moto"], d["contrasto"])
    match.TH_FRAME, match.TH_SEG, match.MIN_LEN = prima
    print(f"segmenti a soglie basse: {len(larghi)}")

    noti = [(s["film_start"], s["film_end"]) for s in segs]
    inizi = d["inizi"]
    candidati = []
    for s in larghi:
        f0, f1 = s[0][0] / FPS, (s[-1][0] + 1) / FPS
        if any(sovrapposizione(f0, f1, a, b) > 0 for a, b in noti):
            continue                       # già trovato dal run principale
        if not any(sovrapposizione(f0, f1, sh["start_time"], sh["end_time"]) >= 1.0
                   for sh in buchi):
            continue                       # non riempie nessun buco
        g0, g1 = s[0][1], s[-1][1]
        parte = int(d["file_di"][g0])
        base = match.base_di(parte, inizi)
        candidati.append({"film_start": f0, "film_end": f1, "parte": parte,
                          "girato_start": (g0 - base) / FPS,
                          "girato_end": (g1 - base + 1) / FPS,
                          "durata": f1 - f0,
                          "score": round(float(np.median([c[2] for c in s])), 3),
                          "n": len(s)})
    print(f"candidati nuovi da verificare: {len(candidati)}")

    t0 = time.time()
    esiti = []
    for i, c in enumerate(candidati, 1):
        esiti.append(controlla(c))
        if i % 20 == 0:
            print(f"  {i}/{len(candidati)} · {(time.time()-t0)/i:.1f} s/candidato", flush=True)
    buoni = [e for e in esiti if e["controllo"] > SOGLIA_VERA]
    (QUI / "recupero.json").write_text(json.dumps(esiti, indent=1))

    print(f"\nconfermati dal controllo (>{SOGLIA_VERA}): {len(buoni)}/{len(esiti)}")

    if "--applica" in sys.argv and buoni:
        # i recuperi entrano nel risultato principale, col loro punteggio di verifica già
        # accanto. Da rifare dopo ogni `match.py --video`, che riscrive i segmenti da capo.
        campi = ("film_start", "film_end", "parte", "girato_start", "girato_end",
                 "durata", "score", "n")
        uniti = segs + [{k: b[k] for k in campi} for b in buoni]
        uniti.sort(key=lambda x: x["film_start"])
        (QUI / "segmenti-video.json").write_text(json.dumps(uniti, indent=1))
        annota_passo("recupero", uniti)
        vecchi = json.loads((QUI / "controllo.json").read_text())
        tutti = vecchi + buoni
        tutti.sort(key=lambda x: x["film_start"])
        (QUI / "controllo.json").write_text(json.dumps(tutti, indent=1))
        print(f"uniti: {len(uniti)} segmenti in segmenti-video.json (e in controllo.json)")
        print("Rigenera con: lavoro.py · artifact.py --offline · timeline.py --miniature")
    if buoni:
        recuperati = {sh["index"] for sh in buchi
                      for b in buoni
                      if sovrapposizione(sh["start_time"], sh["end_time"],
                                         b["film_start"], b["film_end"]) >= 1.0}
        print(f"shot che smettono di essere scoperti: {len(recuperati)}")
        print(f"minuti di film in più: {sum(b['durata'] for b in buoni)/60:.1f}")
