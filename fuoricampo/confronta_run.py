"""Che cosa è cambiato fra due run: `segmenti-video.json` di ieri contro quello di oggi.

Un run nuovo produce un numero — «92%» — e il numero da solo non dice niente su *cosa* si è
mosso. Togliendo FC6 la copertura è rimasta al 92% e sembrava che non fosse successo nulla:
in realtà quindici segmenti avevano cambiato parte, cioè il montato era passato dalla copia
all'originale. Un totale identico può nascondere un rimescolamento completo.

Il confronto è **per shot del film**, non per segmento: i segmenti si spezzano e si fondono
fra un run e l'altro (`estendi` allunga, `buchi` aggiunge), quindi contarli dà una differenza
che non vuol dire niente. Lo shot invece è la stessa cosa nei due run, e la domanda giusta è
se è agganciato, quanto, e a quale parte del girato.

    .venv/bin/python fuoricampo/confronta_run.py PRIMA.json [DOPO.json]

Senza il secondo argomento confronta con `segmenti-video.json`, cioè con lo stato attuale.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from timeline import MANIFEST, QUI, copertura, per_shot


def stato(path: Path, shots) -> tuple[dict, list[dict]]:
    """Per ogni shot: parte del girato che lo copre di più, e frazione coperta."""
    segs = json.loads(path.read_text())
    return ({sh["index"]: (tr[0]["parte"] if tr else None, cop)
             for sh, tr, cop in per_shot(shots, segs)}, segs)


def riga(i: int, a, b) -> str:
    p = lambda x: "—" if x[0] is None else f"FC{x[0]} {x[1]:.0%}"
    return f"  shot {i:03d}  {p(a):>10s} → {p(b):<10s}"


def demo():
    """Uno shot che cambia parte va visto anche se i totali coincidono."""
    a = {1: (2, 0.9), 2: (6, 0.5), 3: (None, 0.0)}
    b = {1: (2, 0.9), 2: (4, 0.5), 3: (None, 0.0)}
    spostati = [i for i in a if None not in (a[i][0], b[i][0]) and a[i][0] != b[i][0]]
    assert spostati == [2], spostati
    assert sum(1 for v in a.values() if v[0] is not None) == \
           sum(1 for v in b.values() if v[0] is not None)
    print("ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
        raise SystemExit
    argomenti = [x for x in sys.argv[1:] if not x.startswith("-")]
    if not argomenti:
        raise SystemExit(__doc__)
    prima = Path(argomenti[0])
    dopo = Path(argomenti[1]) if len(argomenti) > 1 else QUI / "segmenti-video.json"
    shots = json.loads(MANIFEST.read_text())["shots"]

    a, segs_a = stato(prima, shots)
    b, segs_b = stato(dopo, shots)
    cop = lambda s: copertura((x["film_start"], x["film_end"]) for x in s) / 60

    print(f"{prima} →\n{dopo}\n")
    print(f"  segmenti   {len(segs_a):>5d} → {len(segs_b):<5d} ({len(segs_b)-len(segs_a):+d})")
    print(f"  copertura  {cop(segs_a):>5.1f} → {cop(segs_b):<5.1f} min "
          f"({cop(segs_b)-cop(segs_a):+.1f})")
    agg = lambda s: sum(1 for v in s.values() if v[0] is not None)
    print(f"  shot       {agg(a):>5d} → {agg(b):<5d} agganciati su {len(shots)}"
          f" ({agg(b)-agg(a):+d})")

    entrati = [i for i in a if a[i][0] is None and b[i][0] is not None]
    usciti = [i for i in a if a[i][0] is not None and b[i][0] is None]
    spostati = [i for i in a if None not in (a[i][0], b[i][0]) and a[i][0] != b[i][0]]

    for titolo, quali in (("shot agganciati solo dopo", entrati),
                          ("shot agganciati solo prima", usciti),
                          ("shot che cambiano parte del girato", spostati)):
        print(f"\n{titolo}: {len(quali)}")
        for i in sorted(quali)[:25]:
            print(riga(i, a[i], b[i]))
        if len(quali) > 25:
            print(f"  … e altri {len(quali)-25}")

    # la copertura di uno shot può cambiare parecchio senza che cambi la parte
    cambio = sorted((abs(b[i][1] - a[i][1]), i) for i in a
                    if a[i][0] is not None and b[i][0] is not None)
    grossi = [i for d, i in cambio if d >= 0.15]
    print(f"\nshot che restano sulla stessa parte ma cambiano copertura di oltre 15 punti: "
          f"{len(grossi)}")
    for i in sorted(grossi)[:15]:
        print(riga(i, a[i], b[i]))
