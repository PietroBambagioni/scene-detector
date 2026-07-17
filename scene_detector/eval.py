from __future__ import annotations


def boundaries_from_scenes(scenes):
    """Frame di boundary = start_frame di ogni scena tranne la prima."""
    return [s.start_frame for s in scenes[1:]]


def boundaries_from_ranges(ranges):
    """Boundary da una lista di (start, end): start di ogni range tranne il primo."""
    return [r[0] for r in sorted(ranges)[1:]]


def prf1(pred, gt, tol=0):
    """Precision/Recall/F1 su boundary con tolleranza `tol` frame (matching 1-a-1).

    Un boundary predetto conta TP se esiste un GT non ancora accoppiato entro `tol` frame.
    Ritorna dict con precision, recall, f1, tp, fp, fn.
    """
    pred = sorted(pred)
    gt = sorted(gt)
    matched = set()
    tp = 0
    for p in pred:
        best, best_d = None, tol + 1
        for i, g in enumerate(gt):
            if i in matched:
                continue
            d = abs(g - p)
            if d <= tol and d < best_d:
                best, best_d = i, d
        if best is not None:
            matched.add(best)
            tp += 1
    fp = len(pred) - tp
    fn = len(gt) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def evaluate(pred_scenes, gt_ranges, tol=5):
    """F1 di una lista di Scene predette vs ground-truth (lista di (start, end))."""
    return prf1(boundaries_from_scenes(pred_scenes), boundaries_from_ranges(gt_ranges), tol)


def read_scenes_txt(path):
    """Legge un ground-truth: una riga per shot con 'start end' (frame). -> list[(start, end)]."""
    ranges = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                ranges.append((int(parts[0]), int(parts[1])))
    return ranges
