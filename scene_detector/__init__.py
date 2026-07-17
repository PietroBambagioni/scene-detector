from __future__ import annotations

__version__ = "0.1.0"

from .core.scene import Scene
from .core.config import Config
from .detection import build_detector

__all__ = ["Scene", "Config", "build_detector", "__version__"]
