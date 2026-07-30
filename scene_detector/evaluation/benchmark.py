"""Valuta un detector sul test set di SHOT e aggrega i numeri.

Aggregazione **micro**: tp/fp/fn si sommano su tutti i video prima di calcolare P/R/F1, così
un video con 58 shot pesa più di uno con 1. La media degli F1 per-video darebbe a un video di
un solo shot lo stesso peso di un montaggio serrato.
"""
from __future__ import annotations

from dataclasses import replace

from ..core.scene import enforce_min_len
from ..detection.neural import TransNetV2Detector, read_small_frames
from ..io.video import probe
from .eval import boundaries_from_ranges, boundaries_from_scenes, prf, prf1, transition_iou, \
    transitions_from_ranges


def evaluate_video(video_path, gt_ranges, cfg, tol=5, min_iou=0.5):
    """Un video: -> (dict boundary con tp/fp/fn, dict transition, n_shot predetti)."""
    info = probe(video_path)
    vcfg = replace(cfg, video=video_path)

    # decode-once anche per il detector singolo: `detect()` stamperebbe le sue barre per ogni
    # video, e con 50 video l'output del benchmark diventa illeggibile. È anche il motivo per cui
    # qui il detector è fisso e `cfg.detector` non viene letto: `detect_from_frames` la espone
    # solo la via neurale — PySceneDetect decodifica da sé. Passava da `build_detector` con
    # `DetectorKind.transnet` costante, cioè un'indirezione che non sceglieva niente.
    t_det = TransNetV2Detector(vcfg.transnet_weights, vcfg.threshold)
    h, w = t_det.input_size
    frames = read_small_frames(info.path, w, h, total=info.n_frames, progress=False)
    scenes = t_det.detect_from_frames(frames, info)
    scenes = enforce_min_len(scenes, vcfg.min_scene_len)

    b = prf1(boundaries_from_scenes(scenes), boundaries_from_ranges(gt_ranges), tol)
    t = transition_iou(transitions_from_ranges([(s.start_frame, s.end_frame) for s in scenes]),
                       transitions_from_ranges(gt_ranges), min_iou)
    return b, t, len(scenes)


def run(videos, gt, cfg, tol=5, min_iou=0.5, on_video=None):
    """Valuta tutti i video. `videos` = {id: Path}, `gt` = {id: [(start, end), …]}.

    -> dict con i totali micro sui boundary, la media degli IoU sulle transizioni e il
    conteggio dei video. `tol` e `min_iou` viaggiano nel risultato: senza, i numeri non
    sono interpretabili.
    """
    tp = fp = fn = 0
    t_tp = t_fp = t_fn = 0
    ious, n_gt_grad = [], 0

    for vid, path in sorted(videos.items()):
        b, t, n = evaluate_video(path, gt[vid], cfg, tol, min_iou)
        tp, fp, fn = tp + b["tp"], fp + b["fp"], fn + b["fn"]
        t_tp, t_fp, t_fn = t_tp + t["tp"], t_fp + t["fp"], t_fn + t["fn"]
        ious.append((t["mean_iou"], t["matched"]))
        n_gt_grad += sum(1 for (_, e1), (s2, _) in zip(gt[vid], gt[vid][1:]) if s2 != e1 + 1)
        if on_video:
            on_video(vid, b, t, n)

    matched = sum(m for _, m in ious)
    return {
        "n_videos": len(videos),
        "tol": tol,
        "min_iou": min_iou,
        "boundary": prf(tp, fp, fn),
        "transition": {**prf(t_tp, t_fp, t_fn),
                       # media pesata sul numero di accoppiamenti, non sui video
                       "mean_iou": sum(v * m for v, m in ious) / matched if matched else 0.0,
                       "matched": matched},
        "n_gt_graduali": n_gt_grad,
    }
