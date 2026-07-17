from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DetectorKind(str, Enum):
    transnet = "transnet"
    autoshot = "autoshot"
    pyscenedetect = "pyscenedetect"


class SplitMode(str, Enum):
    copy = "copy"          # veloce, snap a keyframe
    reencode = "reencode"  # frame-accurate, lento


@dataclass
class Config:
    video: Path
    output_dir: Path = Path("clips")
    detector: DetectorKind = DetectorKind.transnet
    ensemble: bool = False
    split_mode: SplitMode = SplitMode.copy
    threshold: float = 0.5        # soglia boundary neurale
    min_scene_len: int = 15       # frame minimi per scena
    low_mem: bool = False         # detection neurale in streaming (RAM bounded, no decode-once)
    pyscd_threshold: float = 27.0  # ContentDetector
    agreement_tol: int = 5        # tolleranza (frame) per agreement in ensemble
    transnet_weights: Path | None = None
    autoshot_weights: Path | None = None
