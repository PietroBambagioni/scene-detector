"""Quanto film si ritrova, al variare delle soglie — e quanto è vero.

Il numero di minuti ritrovati sale sempre abbassando le soglie: da solo non dice niente.
Va letto insieme alla precisione, che si misura solo guardando i fotogrammi affiancati
(`coppie.py`). Qui si stampa la curva, la scelta resta una decisione presa a occhio.

    .venv/bin/python fuoricampo/soglie.py
"""
import json, sys
from pathlib import Path
import numpy as np
import match
from impronta import FPS

QUI = Path(__file__).parent
d = np.load(QUI / "candidati.npz")
idx, val, file_di, moto, contrasto = d["idx"], d["val"], d["file_di"], d["moto"], d["contrasto"]
durata_film = len(val) / FPS

print(f"{'th_frame':>9} {'th_seg':>7} {'min_len':>8} {'segmenti':>9} {'minuti':>8} {'% film':>7}")
for th_f, th_s, ml in [(0.70, 0.80, 6), (0.80, 0.85, 6), (0.85, 0.88, 6),
                       (0.85, 0.90, 8), (0.88, 0.90, 8), (0.90, 0.92, 8), (0.92, 0.94, 10)]:
    match.TH_FRAME, match.TH_SEG, match.MIN_LEN = th_f, th_s, ml
    segs = match.segmenti(idx, val, file_di, moto, contrasto)
    tot = sum(len(s) for s in segs) / FPS
    print(f"{th_f:9.2f} {th_s:7.2f} {ml:8d} {len(segs):9d} {tot/60:8.1f} {tot/durata_film:6.1%}")

if len(sys.argv) > 3:      # soglie.py TH_FRAME TH_SEG MIN_LEN [uscita.json]
    match.TH_FRAME, match.TH_SEG, match.MIN_LEN = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
    segs = match.segmenti(idx, val, file_di, moto, contrasto)
    inizi = d["inizi"]
    res = []
    for s in segs:
        g0, g1 = s[0][1], s[-1][1]
        parte = int(file_di[g0]); base = int(inizi[parte - 1])
        res.append({"film_start": s[0][0]/FPS, "film_end": (s[-1][0]+1)/FPS, "parte": parte,
                    "girato_start": (g0-base)/FPS, "girato_end": (g1-base+1)/FPS,
                    "durata": (s[-1][0]+1-s[0][0])/FPS,
                    "score": round(float(np.median([c[2] for c in s])), 3), "n": len(s)})
    out = QUI / (sys.argv[4] if len(sys.argv) > 4 else "segmenti-video.json")
    out.write_text(json.dumps(res, indent=1))
    print(f"-> {out.name}: {len(res)} segmenti, {sum(r['durata'] for r in res)/60:.1f} min")
