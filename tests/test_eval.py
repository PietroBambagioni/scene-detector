from scene_detector.eval import prf1, boundaries_from_scenes, boundaries_from_ranges, evaluate
from scene_detector.scene import scenes_from_ranges


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


def test_evaluate_end_to_end():
    scenes = scenes_from_ranges([(0, 99), (100, 199), (200, 299)], fps=24.0)
    r = evaluate(scenes, [(0, 99), (100, 199), (200, 299)], tol=0)
    assert r["f1"] == 1.0
