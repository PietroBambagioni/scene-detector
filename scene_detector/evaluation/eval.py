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


def f1_curve(pred, gt, tols=(0, 1, 2, 5, 10)):
    """F1 al variare della tolleranza: {tol: f1}.

    Un solo F1 non dice quanto del punteggio venga dallo slack. Se F1 crolla passando da 5 a 0
    frame, i confini sono solo *vicini* a quelli veri — e su una transizione graduale "vicino"
    può voler dire in mezzo alla dissolvenza invece che al suo inizio.
    """
    return {t: prf1(pred, gt, t)["f1"] for t in tols}


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
    fp, fn = len(pred) - tp, len(gt) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "mean_iou": sum(ious) / len(ious) if ious else 0.0,
        "min_iou": min_iou,
        "matched": len(ious),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "tp": tp, "fp": fp, "fn": fn,
    }


def evaluate(pred_scenes, gt_ranges, tol=5, min_iou=0.5):
    """Valuta le Scene predette contro un ground-truth (lista di (start, end)).

    Ritorna precision/recall/f1 sui boundary (chiavi in cima, come prima) più:
    - `tol` — la tolleranza usata, **sempre riportata**: un F1 sui boundary senza la sua
      tolleranza non è un numero interpretabile;
    - `f1_curve` — F1 alle tolleranze 0/1/2/5/10, per vedere quanto del punteggio è slack;
    - `transition` — la metrica range-based, l'unica che vede gli errori di *larghezza*.
    """
    out = prf1(boundaries_from_scenes(pred_scenes), boundaries_from_ranges(gt_ranges), tol)
    pred_ranges = [(s.start_frame, s.end_frame) for s in pred_scenes]
    out["tol"] = tol
    out["f1_curve"] = f1_curve(boundaries_from_scenes(pred_scenes),
                               boundaries_from_ranges(gt_ranges))
    out["transition"] = transition_iou(transitions_from_ranges(pred_ranges),
                                       transitions_from_ranges(gt_ranges), min_iou)
    return out


def read_scenes_txt(path):
    """Legge un ground-truth: una riga per shot con 'start end' (frame). -> list[(start, end)]."""
    ranges = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                ranges.append((int(parts[0]), int(parts[1])))
    return ranges
