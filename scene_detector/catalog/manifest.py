from __future__ import annotations

import json
from pathlib import Path


def build_manifest(video_info, scenes, detector, clip_template="scene-{:03d}.mp4",
                   video_src=None):
    """Costruisce il manifest del catalogo shot (backbone per ASR / VLM / UI).

    I campi `description` e `dialogue` sono placeholder, riempiti dagli step successivi.
    `clip_template=None` (`--split-mode none`): nessuna clip su disco, `clip` resta `None` e
    `video_src` dice alla UI come raggiungere il film originale per i media fragments.
    """
    return {
        "video": Path(video_info.path).name,
        **({"video_src": video_src} if video_src else {}),
        "fps": video_info.fps,
        "n_frames": video_info.n_frames,
        "duration": video_info.duration,
        "detector": detector,
        "n_shots": len(scenes),
        "cast": [],
        "shots": [
            {
                "index": s.index,
                "start_frame": s.start_frame,
                "end_frame": s.end_frame,
                "start_time": round(s.start_time, 3),
                "end_time": round(s.end_time, 3),
                "clip": clip_template.format(s.index + 1) if clip_template else None,
                "confidence": s.confidence,
                "description": None,
                "dialogue": None,
                "characters": [],
            }
            for s in scenes
        ],
    }


def write_manifest(manifest, path):
    Path(path).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def load_manifest(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
