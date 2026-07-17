from __future__ import annotations

from ..core.scene import Scene


def reconcile(a, b, total_frames, fps, tol=5):
    """Riconcilia due liste di Scene (TransNet vs AutoShot) sui boundary.

    Boundary presente in entrambi (entro `tol` frame) -> confidence 1.0 (agreement).
    Boundary in un solo detector -> confidence 0.5 (flag da rivedere).
    Ritorna (scenes_ensemble, flags) dove flags = frame dei boundary in disaccordo.
    """
    ba = sorted({s.start_frame for s in a if s.start_frame > 0})
    bb = sorted({s.start_frame for s in b if s.start_frame > 0})

    merged = []  # (frame, confidence, agreed)
    used_b = set()
    for fa in ba:
        match = next((fb for fb in bb if fb not in used_b and abs(fb - fa) <= tol), None)
        if match is not None:
            used_b.add(match)
            merged.append(((fa + match) // 2, 1.0, True))
        else:
            merged.append((fa, 0.5, False))
    for fb in bb:
        if fb not in used_b:
            merged.append((fb, 0.5, False))
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
