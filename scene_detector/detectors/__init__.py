from __future__ import annotations

from ..config import DetectorKind
from .base import SceneDetector
from .pyscenedetect_detector import PySceneDetectDetector
from .transnetv2_detector import TransNetV2Detector
from .autoshot_detector import AutoShotDetector

__all__ = [
    "SceneDetector",
    "PySceneDetectDetector",
    "TransNetV2Detector",
    "AutoShotDetector",
    "build_detector",
]


def build_detector(kind, cfg) -> SceneDetector:
    if kind == DetectorKind.transnet:
        return TransNetV2Detector(cfg.transnet_weights, cfg.threshold, cfg.low_mem)
    if kind == DetectorKind.autoshot:
        return AutoShotDetector(cfg.autoshot_weights, cfg.threshold, cfg.low_mem)
    if kind == DetectorKind.pyscenedetect:
        return PySceneDetectDetector(cfg.pyscd_threshold, cfg.min_scene_len)
    raise ValueError(f"detector sconosciuto: {kind}")
