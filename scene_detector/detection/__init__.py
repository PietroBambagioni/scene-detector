from __future__ import annotations

from ..core.config import DetectorKind
from .neural import AutoShotDetector, TransNetV2Detector
from .pyscenedetect import PySceneDetectDetector

__all__ = ["build_detector"]


def build_detector(kind, cfg):
    if kind == DetectorKind.transnet:
        return TransNetV2Detector(cfg.transnet_weights, cfg.threshold, cfg.min_peak)
    if kind == DetectorKind.autoshot:
        return AutoShotDetector(cfg.autoshot_weights, cfg.threshold, cfg.min_peak)
    if kind == DetectorKind.pyscenedetect:
        return PySceneDetectDetector(min_scene_len=cfg.min_scene_len)
    raise ValueError(f"detector sconosciuto: {kind}")
