from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..io.video import VideoInfo
from ..scene import Scene


@runtime_checkable
class SceneDetector(Protocol):
    name: str

    def detect(self, video: VideoInfo) -> "list[Scene]":
        ...
