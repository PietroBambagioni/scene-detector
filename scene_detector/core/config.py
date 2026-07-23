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
    none = "none"          # non taglia: la UI riproduce il film intero con media fragments


@dataclass
class Config:
    video: Path
    output_dir: Path = Path("clips")
    detector: DetectorKind = DetectorKind.transnet
    ensemble: bool = False
    split_mode: SplitMode = SplitMode.copy
    threshold: float = 0.5        # soglia boundary neurale
    min_scene_len: int = 15       # frame minimi per scena
    agreement_tol: int = 5        # tolleranza (frame) per agreement in ensemble
    transnet_weights: Path | None = None
    autoshot_weights: Path | None = None
    # trascrizione dialoghi (ASR)
    asr: bool = False
    asr_model: str = "large-v3-turbo"
    asr_lang: str | None = None
    asr_threads: int = 0
    # descrizione visiva per shot (VLM)
    vlm: bool = False
    vlm_model: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit"
    vlm_frames: int = 3
    # riconoscimento personaggi (faces)
    faces: bool = False
    faces_gallery: Path | None = None
    faces_frames: int = 6
    faces_threshold: float = 0.5
    faces_min_score: float = 0.5
    faces_min_px: int = 50        # lato minimo del bbox: sotto, l'embedding e' rumore
    # taglio clip
    jobs: int = 0                 # processi ffmpeg paralleli (0 = auto)
