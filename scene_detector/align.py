from __future__ import annotations


def assign_dialogue(shots, segments):
    """Assegna a ogni shot il testo dei segmenti il cui punto medio cade nello shot.

    Ogni segmento finisce in esattamente uno shot (nessuna duplicazione). I segmenti oltre
    l'ultimo confine (arrotondamenti) vanno nell'ultimo shot. `shots` è la lista di dict del
    manifest, mutata in-place (campo `dialogue`).
    """
    n = len(shots)
    buckets = [[] for _ in range(n)]
    for seg in segments:
        mid = (seg["start"] + seg["end"]) / 2
        for i, shot in enumerate(shots):
            last = i == n - 1
            if (shot["start_time"] <= mid < shot["end_time"]) or (last and mid >= shot["start_time"]):
                buckets[i].append(seg["text"])
                break
    for i, shot in enumerate(shots):
        shot["dialogue"] = " ".join(buckets[i]) if buckets[i] else None
    return shots
