from __future__ import annotations

from ..core.scene import Scene


def reconcile(a, b, total_frames, fps, probs, tol=5):
    """Riconcilia due liste di Scene (TransNet vs AutoShot) sui boundary.

    La **confidenza** di ogni boundary è la prob per-frame di TransNetV2 (`probs`) al taglio —
    uno score continuo e calibrato al posto del vecchio flag binario 1.0/0.5. L'accordo tra i due
    detector resta come segnale separato in `flags` (boundary in disaccordo, da rivedere).
    Ritorna (scenes_ensemble, flags) dove flags = frame dei boundary in disaccordo.
    """
    n = len(probs)
    conf_at = lambda f: float(probs[min(max(f - 1, 0), n - 1)])  # prob del taglio che apre a `f`

    ba = sorted({s.start_frame for s in a if s.start_frame > 0})
    bb = sorted({s.start_frame for s in b if s.start_frame > 0})

    merged = []  # (frame, confidence, agreed)
    used_b = set()
    for fa in ba:
        match = next((fb for fb in bb if fb not in used_b and abs(fb - fa) <= tol), None)
        if match is not None:
            used_b.add(match)
            merged.append(((fa + match) // 2, conf_at(fa), True))
        else:
            merged.append((fa, conf_at(fa), False))
    for fb in bb:
        if fb not in used_b:
            merged.append((fb, conf_at(fb), False))
    merged.sort()

    bounds = [0] + [m[0] for m in merged] + [total_frames]
    confs = [1.0] + [m[1] for m in merged]
    scenes = []
    for i in range(len(bounds) - 1):
        start, end = bounds[i], bounds[i + 1] - 1
        if end < start:
            continue
        scenes.append(Scene(len(scenes), start, end, fps, "ensemble", confs[i]))

    flags = [m[0] for m in merged if not m[2]]
    return scenes, flags
