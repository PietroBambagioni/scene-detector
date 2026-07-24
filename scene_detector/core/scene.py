from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Scene:
    index: int
    start_frame: int
    end_frame: int  # inclusivo
    fps: float
    source: str = ""
    confidence: float = 1.0
    # (start, end) inclusivi della giunta che **apre** questa scena, se è una transizione
    # graduale; None per il primo shot e per gli stacchi netti. Vedi `runs_to_ranges`.
    transition: tuple | None = None

    @property
    def n_frames(self) -> int:
        return self.end_frame - self.start_frame + 1

    @property
    def start_time(self) -> float:
        return self.start_frame / self.fps

    @property
    def end_time(self) -> float:
        return (self.end_frame + 1) / self.fps


def scenes_from_ranges(ranges, fps, source="", confidences=None, transitions=None):
    """ranges = lista di (start, end) inclusivi, contigui. -> list[Scene].

    `confidences` e `transitions` (opzionali) sono allineate a `ranges`; se assenti si usano i
    default di `Scene` (1.0 e None).
    """
    def at(seq, i, default):
        return default if seq is None else seq[i]

    return [Scene(i, s, e, fps, source, at(confidences, i, 1.0), at(transitions, i, None))
            for i, (s, e) in enumerate(ranges)]


def enforce_min_len(scenes, min_len):
    """Fonde nella precedente ogni scena piu' corta di min_len frame."""
    if not scenes:
        return scenes
    out = [scenes[0]]
    for sc in scenes[1:]:
        if sc.n_frames < min_len:
            out[-1] = replace(out[-1], end_frame=sc.end_frame)
        else:
            out.append(sc)
    return [replace(sc, index=i) for i, sc in enumerate(out)]
