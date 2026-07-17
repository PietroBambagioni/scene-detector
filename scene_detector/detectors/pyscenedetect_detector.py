from __future__ import annotations

from ..scene import scenes_from_ranges


class PySceneDetectDetector:
    name = "pyscenedetect"

    def __init__(self, threshold=27.0, min_scene_len=15, adaptive=False):
        self.threshold = threshold
        self.min_scene_len = min_scene_len
        self.adaptive = adaptive

    def detect(self, video):
        from scenedetect import (
            open_video, SceneManager, ContentDetector, AdaptiveDetector,
        )

        v = open_video(str(video.path))
        sm = SceneManager()
        det = (
            AdaptiveDetector(min_scene_len=self.min_scene_len)
            if self.adaptive
            else ContentDetector(threshold=self.threshold, min_scene_len=self.min_scene_len)
        )
        sm.add_detector(det)
        sm.detect_scenes(v, show_progress=False)

        # scene_list: (start, end) FrameTimecode, end = start della scena successiva (esclusivo)
        ranges = [(s.get_frames(), e.get_frames() - 1) for s, e in sm.get_scene_list()]
        if not ranges:
            ranges = [(0, max(0, video.n_frames - 1))]
        return scenes_from_ranges(ranges, video.fps, self.name)
