from __future__ import annotations


def assign_dialogue(shots, segments):
    """Assegna a ogni shot il testo dei segmenti il cui punto medio cade nello shot.

    Ogni segmento finisce in esattamente uno shot (nessuna duplicazione). I segmenti oltre
    l'ultimo confine (arrotondamenti) vanno nell'ultimo shot. `shots` è la lista di dict del
    manifest, mutata in-place (campo `dialogue`).

    Shot contigui e ordinati + segmenti ordinati per punto medio → scansione lineare con un
    puntatore che non torna indietro: O(shot + segmenti) invece di O(shot × segmenti).
    """
    n = len(shots)
    buckets = [[] for _ in range(n)]
    i = 0
    for seg in sorted(segments, key=lambda s: s["start"] + s["end"]):
        mid = (seg["start"] + seg["end"]) / 2
        while i < n - 1 and mid >= shots[i]["end_time"]:
            i += 1
        if mid >= shots[i]["start_time"] or i == n - 1:
            buckets[i].append(seg["text"])
    for i, shot in enumerate(shots):
        shot["dialogue"] = " ".join(buckets[i]) if buckets[i] else None
    return shots
