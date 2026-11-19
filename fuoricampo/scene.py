"""Le scene lunghe e ferme, che il voting sequenziale non vede.

`match.py` cerca **diagonali**: una corsa di fotogrammi in cui il girato avanza insieme al
film. Funziona finché ogni fotogramma ha un candidato migliore chiaro. Su un primo piano di
cinque minuti che si muove poco, invece, ogni fotogramma somiglia a decine di punti del
girato: il candidato migliore salta di qua e di là e la diagonale non si forma mai — anche con
il 54% dei fotogrammi sopra 0,75, come nello shot 110.

Qui si vota diversamente: si prendono **tutti** i candidati di tutti i fotogrammi dello shot,
si guarda quale *offset* propongono, e si tiene quello più votato. Non conta che i singoli
match siano ordinati, conta che siano d'accordo. Poi decide `controllo.py` come sempre.

    .venv/bin/python fuoricampo/scene.py [--applica] [--solo=13,19,69,...]

`--solo` tiene solo gli shot elencati. Serve perché qui la verifica automatica non basta: le
proposte vanno guardate affiancate una per una — 5 vere su 7 nel run del 25 agosto, 5 su 7 in
quello senza FC6, cioè il 71% contro il 98% del resto. Applicarle tutte peggiora il risultato.
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np

from controllo import controlla
from impronta import FPS
from impronta import riduci, smonta_gradiente
from match import MIN_CONTRASTO, MIN_MOTO, contrasto_film, moto_film
from timeline import MANIFEST, QUI, annota_passo, copertura, sovrapposizione

SOGLIA_VERA = 0.648
MIN_VOTI = 4        # sotto questo l'accordo è casuale
BIN = 1.0           # tolleranza dell'offset, in secondi
QUANTI = 3          # offset più votati da verificare per scena


def scoperti(shots, segs):
    fuori = []
    for sh in shots:
        dur = max(sh["end_time"] - sh["start_time"], 1e-6)
        cop = copertura((max(sh["start_time"], s["film_start"]),
                         min(sh["end_time"], s["film_end"])) for s in segs
                        if sovrapposizione(sh["start_time"], sh["end_time"],
                                           s["film_start"], s["film_end"]) > 0)
        if cop < 1.0 or cop / dur < 0.10:
            fuori.append(sh)
    return fuori


def offset_votati(sh, d, contrasto, moto):
    """Gli offset su cui i candidati dello shot si trovano d'accordo, dal più votato."""
    idx, val, file_di, inizi = d["idx"], d["val"], d["file_di"], d["inizi"]
    i0 = int(sh["start_time"] * FPS)
    i1 = min(int(sh["end_time"] * FPS), len(val))
    # Valgono le stesse due condizioni del matcher, e per la stessa ragione: cambiare **come**
    # si vota non rende verificabile quello che non lo è. Su un cartello fermo l'accordo fra
    # candidati è accordo su niente — è così che il cartello di testa tornava agganciato a una
    # targa incisa, con 0,87 di controllo.
    if (i1 - i0 < 2
            or float(np.median(contrasto[i0:i1])) < MIN_CONTRASTO
            or float(np.median(moto[i0:i1])) < MIN_MOTO):
        return []
    urna = {}
    for i in range(i0, i1):
        for c in range(idx.shape[1]):
            if val[i, c] < 0.70:
                break
            g = int(idx[i, c])
            parte = int(file_di[g])
            off = (g - int(inizi[parte - 1])) / FPS - i / FPS
            chiave = (parte, round(off / BIN))
            voce = urna.setdefault(chiave, [0, 0.0])
            voce[0] += 1
            voce[1] = max(voce[1], float(val[i, c]))
    vincitori = sorted(urna.items(), key=lambda kv: -kv[1][0])[:QUANTI]
    return [(parte, b * BIN, n, mx) for (parte, b), (n, mx) in vincitori if n >= MIN_VOTI]


if __name__ == "__main__":
    d = np.load(QUI / "candidati.npz")
    segs = json.loads((QUI / "segmenti-video.json").read_text())
    shots = json.loads(MANIFEST.read_text())["shots"]
    grezzo = np.load(QUI / "dati" / "Anna.npy")
    contrasto = contrasto_film(grezzo)
    moto = moto_film(smonta_gradiente(riduci(grezzo.astype(np.float32))))

    proposte = []
    for sh in scoperti(shots, segs):
        for parte, off, voti, mx in offset_votati(sh, d, contrasto, moto):
            if sh["start_time"] + off < 0:
                continue
            proposte.append({
                "film_start": sh["start_time"], "film_end": sh["end_time"],
                "parte": parte, "girato_start": sh["start_time"] + off,
                "girato_end": sh["end_time"] + off,
                "durata": sh["end_time"] - sh["start_time"],
                "score": round(mx, 3), "n": voti, "shot": sh["index"]})
    print(f"scene scoperte con un offset votato: "
          f"{len({p['shot'] for p in proposte})} · {len(proposte)} ipotesi da verificare")

    t0 = time.time()
    esiti = [controlla(p) for p in proposte]
    print(f"verificate in {time.time()-t0:.0f}s")
    # per ogni shot si tiene solo l'ipotesi migliore, e solo se batte i casuali
    meglio = {}
    for e in esiti:
        if e["controllo"] > SOGLIA_VERA and e["controllo"] > meglio.get(e["shot"], {}).get("controllo", 0):
            meglio[e["shot"]] = e
    buoni = list(meglio.values())
    (QUI / "scene.json").write_text(json.dumps(esiti, indent=1))
    print(f"confermate: {len(buoni)} scene · {sum(b['durata'] for b in buoni)/60:.1f} min")
    for b in sorted(buoni, key=lambda x: -x["durata"])[:8]:
        print(f"  shot {b['shot']:03d} · {b['durata']:5.0f}s · film {b['film_start']/60:6.1f}m "
              f"-> FC{b['parte']} {b['girato_start']/60:6.1f}m · controllo {b['controllo']:.2f}")

    solo = next((a for a in sys.argv if a.startswith("--solo=")), None)
    if solo:
        tenuti = {int(x) for x in solo.removeprefix("--solo=").split(",")}
        buoni = [b for b in buoni if b["shot"] in tenuti]
        print(f"tenuti a mano: {len(buoni)} · {sum(b['durata'] for b in buoni)/60:.1f} min")
    if "--applica" in sys.argv and buoni:
        campi = ("film_start", "film_end", "parte", "girato_start", "girato_end",
                 "durata", "score", "n")
        uniti = segs + [{k: b[k] for k in campi} for b in buoni]
        uniti.sort(key=lambda x: x["film_start"])
        (QUI / "segmenti-video.json").write_text(json.dumps(uniti, indent=1))
        annota_passo("scene", uniti)
        ctrl = json.loads((QUI / "controllo.json").read_text()) + [
            {k: v for k, v in b.items() if k != "shot"} for b in buoni]
        ctrl.sort(key=lambda x: x["film_start"])
        (QUI / "controllo.json").write_text(json.dumps(ctrl, indent=1))
        prima = copertura((s["film_start"], s["film_end"]) for s in segs)
        dopo = copertura((s["film_start"], s["film_end"]) for s in uniti)
        print(f"\ncopertura: {prima/60:.1f} -> {dopo/60:.1f} min ({prima/12829:.0%} -> {dopo/12829:.0%})")
