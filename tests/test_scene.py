from scene_detector.scene import Scene, scenes_from_ranges, enforce_min_len
from scene_detector.detectors._neural import probs_to_ranges


def test_scene_properties():
    s = Scene(0, 0, 23, fps=24.0)
    assert s.n_frames == 24
    assert s.start_time == 0.0
    assert abs(s.end_time - 1.0) < 1e-9


def test_scenes_from_ranges():
    scenes = scenes_from_ranges([(0, 9), (10, 19)], fps=10.0, source="x")
    assert len(scenes) == 2
    assert scenes[1].start_time == 1.0
    assert scenes[0].source == "x"


def test_enforce_min_len_merges_short():
    scenes = scenes_from_ranges([(0, 20), (21, 22), (23, 60)], fps=24.0)
    merged = enforce_min_len(scenes, min_len=15)
    assert len(merged) == 2
    assert merged[0].end_frame == 22  # scena corta fusa nella precedente
    assert [s.index for s in merged] == [0, 1]


def test_probs_to_ranges():
    probs = [0.0] * 40
    probs[20] = 0.9
    assert probs_to_ranges(probs, threshold=0.5, min_scene_len=3) == [(0, 20), (21, 39)]
