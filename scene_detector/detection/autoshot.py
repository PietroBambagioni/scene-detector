from __future__ import annotations

from pathlib import Path

from ..core.scene import scenes_from_ranges
from .neural import read_small_frames, stream_small_windows, probs_to_ranges


class AutoShotDetector:
    """[OPZIONALE] Seconda opinione neurale (NAS-based). Stesso contratto di TransNetV2."""

    name = "autoshot"
    input_size = (27, 48)  # (H, W)

    def __init__(self, weights=None, threshold=0.5, low_mem=False):
        self.weights = Path(weights) if weights else None
        self.threshold = threshold
        self.low_mem = low_mem

    def detect(self, video):
        h, w = self.input_size
        if self.low_mem:
            streamer = stream_small_windows(video.path, w, h, total=video.n_frames,
                                            desc=f"[{self.name}] stream")
            probs = self._load_model().predict_stream(streamer)
            ranges = probs_to_ranges(probs, self.threshold)
            return scenes_from_ranges(ranges, video.fps, self.name)
        frames = read_small_frames(video.path, w, h, total=video.n_frames,
                                   desc=f"[{self.name}] frames")
        return self.detect_from_frames(frames, video)

    def detect_from_frames(self, frames, video):
        """Predizione da frame già decodificati (uint8[N,27,48,3]).

        Separata da `detect` per condividere una singola decodifica in ensemble."""
        model = self._load_model()  # espone .predict(uint8[N,27,48,3]) -> float[N]
        probs = model.predict(frames)
        ranges = probs_to_ranges(probs, self.threshold)
        return scenes_from_ranges(ranges, video.fps, self.name)

    def _load_model(self):
        """Costruisce TransNetV2Supernet e carica i pesi AutoShot (predict con windowing)."""
        try:
            import torch  # noqa: F401
        except ImportError as e:
            raise RuntimeError("AutoShot richiede torch: pip install '.[neural]'") from e
        if self.weights is None or not self.weights.exists():
            raise RuntimeError(
                "Pesi AutoShot mancanti (ckpt_0_200_0.pth da Baidu). "
                "Vedi README > 'AutoShot', poi passa --autoshot-weights PATH."
            )
        from .models.wrapper import AutoShotPredictor
        return AutoShotPredictor(self.weights)
