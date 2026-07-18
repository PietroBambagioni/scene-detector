from scene_detector.detection.confidence import reconcile
from scene_detector.core.scene import scenes_from_ranges


def _probs(n, spikes):
    """Array di prob per-frame lungo n, con `spikes` = {frame: prob}."""
    p = [0.0] * n
    for f, v in spikes.items():
        p[f] = v
    return p


def test_reconcile_agreement_continuous_confidence():
    a = scenes_from_ranges([(0, 99), (100, 199), (200, 299)], 24.0)
    b = scenes_from_ranges([(0, 99), (100, 199), (200, 299)], 24.0)
    probs = _probs(300, {99: 0.9, 199: 0.8})  # taglio a start s -> prob a s-1
    scenes, flags = reconcile(a, b, 300, 24.0, probs, tol=5)
    assert flags == []
    assert len(scenes) == 3
    assert scenes[0].confidence == 1.0          # inizio film
    assert scenes[1].confidence == 0.9          # prob continua, non più 1.0 binario
    assert scenes[2].confidence == 0.8


def test_reconcile_within_tolerance_uses_transnet_prob():
    a = scenes_from_ranges([(0, 99), (100, 299)], 24.0)   # boundary 100 (TransNet)
    b = scenes_from_ranges([(0, 102), (103, 299)], 24.0)  # boundary 103, |103-100|<=5
    probs = _probs(300, {99: 0.7})
    scenes, flags = reconcile(a, b, 300, 24.0, probs, tol=5)
    assert flags == []
    assert len(scenes) == 2
    assert scenes[1].confidence == 0.7          # confidenza = prob di TransNet al suo boundary


def test_reconcile_disagreement_flags_transnet_only():
    a = scenes_from_ranges([(0, 99), (100, 199), (200, 299)], 24.0)  # boundary 100, 200
    b = scenes_from_ranges([(0, 99), (100, 299)], 24.0)              # boundary 100 solo
    probs = _probs(300, {99: 0.9, 199: 0.95})
    scenes, flags = reconcile(a, b, 300, 24.0, probs, tol=5)
    assert flags == [200]                        # 200 presente solo in a
    assert scenes[2].confidence == 0.95          # confidenza continua anche sul boundary in disaccordo


def test_reconcile_autoshot_only_boundary_gets_low_confidence():
    # AutoShot vede un taglio dove TransNet non ha sparato -> confidenza bassa e calibrata,
    # non un magico 0.5: è esattamente il senso di "prob per-frame come confidenza".
    a = scenes_from_ranges([(0, 99), (100, 299)], 24.0)              # TransNet: boundary 100
    b = scenes_from_ranges([(0, 99), (100, 249), (250, 299)], 24.0)  # AutoShot: 100 + 250
    probs = _probs(300, {99: 0.9, 249: 0.12})   # a 249 TransNet è basso (non ha visto il taglio)
    scenes, flags = reconcile(a, b, 300, 24.0, probs, tol=5)
    assert flags == [250]
    assert len(scenes) == 3
    assert scenes[1].confidence == 0.9
    assert scenes[2].confidence == 0.12          # boundary solo-AutoShot: prob TransNet bassa
