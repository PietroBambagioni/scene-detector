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

    @property
    def n_frames(self) -> int:
        return self.end_frame - self.start_frame + 1

    @property
    def start_time(self) -> float:
        return self.start_frame / self.fps

    @property
    def end_time(self) -> float:
        return (self.end_frame + 1) / self.fps


def scenes_from_ranges(ranges, fps, source="", confidences=None):
    """ranges = lista di (start, end) inclusivi, contigui. -> list[Scene].

    `confidences` (opzionale) = confidenza per range, allineata a `ranges`; se assente
    ogni scena usa il default 1.0.
    """
    if confidences is None:
        return [Scene(i, s, e, fps, source) for i, (s, e) in enumerate(ranges)]
    return [Scene(i, s, e, fps, source, confidences[i]) for i, (s, e) in enumerate(ranges)]


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
