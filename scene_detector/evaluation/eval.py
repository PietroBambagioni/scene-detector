from __future__ import annotations


def boundaries_from_scenes(scenes):
    """Frame di boundary = start_frame di ogni scena tranne la prima."""
    return [s.start_frame for s in scenes[1:]]


def boundaries_from_ranges(ranges):
    """Boundary da una lista di (start, end): start di ogni range tranne il primo."""
    return [r[0] for r in sorted(ranges)[1:]]


def prf(tp, fp, fn):
    """Precision/Recall/F1 da tp/fp/fn. -> dict con le sei chiavi."""
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "tp": tp, "fp": fp, "fn": fn}


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
    return prf(tp, len(pred) - tp, len(gt) - tp)


# ------------------------------------------------------- transizioni (range) ---
# Il matching sui boundary è cieco alla **larghezza**: dà ragione anche sbagliando di 15 frame
# su una dissolvenza, perché confronta punti con punti. Si può avere F1 0,82 e transition IoU
# 0,20 nello stesso modello. Qui la transizione è un intervallo e si misura la sovrapposizione.

def transitions_from_ranges(ranges):
    """Le transizioni implicite in una lista di shot (start, end) inclusivi e ordinati.

    Fra due shot consecutivi:
    - **contigui** (`s2 == e1 + 1`) → *hard cut*: transizione di larghezza minima, i due frame a
      cavallo dello stacco → `(e1, s2)`. Non zero, o l'IoU non sarebbe definito.
    - **con un buco** → transizione *graduale* (dissolvenza, fade, wipe): il buco **è** la
      transizione → `(e1 + 1, s2 - 1)`.

    Un ground-truth annotato solo a stacchi netti produce quindi solo transizioni da 2 frame:
    è corretto, ed è il motivo per cui su un film a soli hard cut questa metrica dice poco.
    """
    rs = sorted(ranges)
    out = []
    for (_, e1), (s2, _) in zip(rs, rs[1:]):
        out.append((e1, s2) if s2 == e1 + 1 else (e1 + 1, s2 - 1))
    return out


def transitions_from_scenes(scenes):
    """Le transizioni **come le ha delimitate il detector**: una per shot, tranne il primo.

    `transitions_from_ranges` non basta per i predetti: con `runs_to_ranges` gli shot sono
    contigui e la larghezza della giunta vive in `Scene.transition`, quindi dai soli range ogni
    dissolvenza torna uno stacco da 2 frame — IoU 0,04 su una da 24 frame che il detector aveva
    delimitato per intero. Stessa forma del banco (`prove/runs_ab.runs_above`): una corsa `i..j`
    è `(i, j+1)`, che per lo stacco netto si riduce a `(e1, s2)`.
    """
    return [(s.transition[0] if s.transition else s.start_frame - 1, s.start_frame)
            for s in scenes[1:]]


def iou(a, b):
    """IoU di due intervalli di frame inclusivi."""
    inter = min(a[1], b[1]) - max(a[0], b[0]) + 1
    if inter <= 0:
        return 0.0
    return inter / (max(a[1], b[1]) - min(a[0], b[0]) + 1)


def transition_iou(pred, gt, min_iou=0.5):
    """Metrica range-based: quanto bene *delimitiamo* le transizioni, non solo dove stanno.

    Accoppiamento greedy per IoU decrescente (indipendente dall'ordine delle liste). `mean_iou`
    è la media sugli accoppiamenti trovati — quanto sono precise le transizioni che becchiamo;
    precision/recall/f1 contano TP solo gli accoppiamenti con IoU >= `min_iou`.
    """
    pairs = sorted(((iou(p, g), i, j) for i, p in enumerate(pred) for j, g in enumerate(gt)),
                   reverse=True)
    used_p, used_g, ious = set(), set(), []
    for v, i, j in pairs:
        if v <= 0:
            break
        if i in used_p or j in used_g:
            continue
        used_p.add(i)
        used_g.add(j)
        ious.append(v)

    tp = sum(1 for v in ious if v >= min_iou)
    return {
        **prf(tp, len(pred) - tp, len(gt) - tp),
        "mean_iou": sum(ious) / len(ious) if ious else 0.0,
        "min_iou": min_iou,
        "matched": len(ious),
    }
