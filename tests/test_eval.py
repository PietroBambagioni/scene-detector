from scene_detector.evaluation.eval import (boundaries_from_ranges, boundaries_from_scenes,
                                            iou, prf1, transition_iou, transitions_from_ranges)
from scene_detector.core.scene import scenes_from_ranges


def test_prf1_perfect():
    r = prf1([100, 200, 300], [100, 200, 300], tol=0)
    assert r["f1"] == 1.0 and r["tp"] == 3 and r["fp"] == 0 and r["fn"] == 0


def test_prf1_tolerance():
    r = prf1([102, 199], [100, 200], tol=3)
    assert r["tp"] == 2 and r["f1"] == 1.0


def test_prf1_fp_fn():
    r = prf1([100, 500], [100, 200], tol=2)  # 100 match, 500 FP, 200 FN
    assert r["tp"] == 1 and r["fp"] == 1 and r["fn"] == 1
    assert abs(r["precision"] - 0.5) < 1e-9 and abs(r["recall"] - 0.5) < 1e-9


def test_boundaries():
    scenes = scenes_from_ranges([(0, 99), (100, 199), (200, 299)], fps=24.0)
    assert boundaries_from_scenes(scenes) == [100, 200]
    assert boundaries_from_ranges([(0, 99), (100, 199), (200, 299)]) == [100, 200]


# ------------------------------------------------------- transizioni (range) ---

def test_transitions_hard_cut_e_graduale():
    # shot contigui = hard cut (i due frame a cavallo); buco = transizione graduale
    assert transitions_from_ranges([(0, 99), (100, 199)]) == [(99, 100)]
    assert transitions_from_ranges([(0, 99), (124, 199)]) == [(100, 123)]


def test_iou_intervalli():
    assert iou((0, 9), (0, 9)) == 1.0
    assert iou((0, 9), (10, 19)) == 0.0          # adiacenti ma disgiunti
    assert iou((0, 9), (5, 14)) == 5 / 15        # 5 frame in comune su 15 di unione


def test_transition_iou_perfetto():
    r = transition_iou([(100, 123)], [(100, 123)])
    assert r["mean_iou"] == 1.0 and r["f1"] == 1.0


def test_f1_alto_ma_iou_pessimo_sulla_dissolvenza():
    """Il caso per cui esiste questa metrica.

    Ground truth: dissolvenza di 24 frame (100-123). Il detector piazza un punto secco a 111,
    cioè **in mezzo** alla dissolvenza. Il matching sui boundary lo promuove — è a 11 frame dal
    GT, dentro una tolleranza generosa — ma la transizione non è affatto delimitata.
    """
    gt = [(0, 99), (124, 299)]                    # buco 100-123 = dissolvenza
    pred = scenes_from_ranges([(0, 110), (111, 299)], fps=24.0)   # taglio secco a 111

    b = prf1(boundaries_from_scenes(pred), boundaries_from_ranges(gt), tol=15)
    t = transition_iou(transitions_from_ranges([(s.start_frame, s.end_frame) for s in pred]),
                       transitions_from_ranges(gt))
    assert b["f1"] == 1.0                         # i boundary dicono: perfetto
    assert t["mean_iou"] < 0.15                   # le transizioni dicono: sbagliato
    assert t["f1"] == 0.0                         # e sotto min_iou non è nemmeno un TP


def test_transition_iou_ignora_le_coppie_disgiunte():
    # una predizione lontanissima non si accoppia con nulla: 0 match, tutto FP/FN
    r = transition_iou([(1000, 1010)], [(100, 123)])
    assert r["matched"] == 0 and r["tp"] == 0 and r["fp"] == 1 and r["fn"] == 1


def test_transition_iou_matching_indipendente_dall_ordine():
    a = transition_iou([(100, 123), (200, 210)], [(200, 210), (100, 123)])
    b = transition_iou([(200, 210), (100, 123)], [(100, 123), (200, 210)])
    assert a["mean_iou"] == b["mean_iou"] == 1.0


def test_il_benchmark_vede_la_larghezza_che_il_detector_ha_delimitato():
    """Con `runs_to_ranges` gli shot sono contigui e la larghezza vive in `Scene.transition`:
    ricavare le transizioni dai soli range dava IoU 0,04 su una dissolvenza delimitata per intero,
    cioe' il comando di benchmark non misurava proprio la cosa per cui le corse esistono."""
    import numpy as np

    from scene_detector.detection.neural import runs_to_ranges
    from scene_detector.evaluation.eval import transitions_from_scenes

    probs = np.zeros(300)
    probs[100:124] = 0.6          # dissolvenza: corsa 100..123
    probs[200] = 0.9              # stacco netto
    ranges, tr = runs_to_ranges(probs, 0.05)
    scenes = scenes_from_ranges(ranges, 25.0, transitions=tr)
    gt = transitions_from_ranges([(0, 99), (124, 200), (201, 299)])     # buco 100..123 + stacco

    pred = transitions_from_scenes(scenes)
    assert pred == [(100, 124), (200, 201)]       # corsa i..j -> (i, j+1); lo stacco resta (e1, s2)
    assert transition_iou(pred, gt)["tp"] == 2

    # controprova: dai soli range la dissolvenza e' uno stacco da 2 frame e non e' un TP
    ciechi = transitions_from_ranges(ranges)
    assert ciechi[0] == (123, 124)
    assert transition_iou(ciechi, gt)["tp"] == 1
