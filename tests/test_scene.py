from scene_detector.core.scene import Scene, scenes_from_ranges, enforce_min_len
from scene_detector.detection.neural import probs_to_ranges, boundary_confidences


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


def test_scenes_from_ranges_with_confidences():
    scenes = scenes_from_ranges([(0, 9), (10, 19)], fps=10.0, confidences=[1.0, 0.42])
    assert [s.confidence for s in scenes] == [1.0, 0.42]


def test_boundary_confidences():
    probs = [0.0] * 40
    probs[19] = 0.9  # taglio: apre lo shot che inizia a 20
    ranges = probs_to_ranges(probs, threshold=0.5)  # [(0,19),(20,39)]
    confs = boundary_confidences(ranges, probs)
    assert confs[0] == 1.0        # primo shot: inizio film
    assert confs[1] == 0.9        # prob del taglio a 19 (apre lo shot che inizia a 20)


def test_boundary_confidences_single_range():
    # nessun taglio -> un solo shot, confidenza inizio film
    assert boundary_confidences([(0, 39)], [0.0] * 40) == [1.0]


def test_enforce_min_len_merges_short():
    scenes = scenes_from_ranges([(0, 20), (21, 22), (23, 60)], fps=24.0)
    merged = enforce_min_len(scenes, min_len=15)
    assert len(merged) == 2
    assert merged[0].end_frame == 22  # scena corta fusa nella precedente
    assert [s.index for s in merged] == [0, 1]


def test_probs_to_ranges():
    probs = [0.0] * 40
    probs[20] = 0.9
    assert probs_to_ranges(probs, threshold=0.5) == [(0, 20), (21, 39)]


def test_probs_to_ranges_keeps_short_boundary():
    # probs_to_ranges traduce solo prob->range: il boundary corto NON è soppresso qui
    # (il vincolo min_scene_len è di enforce_min_len). Boundary a 2 -> due range.
    probs = [0.0] * 20
    probs[2] = 0.9
    assert probs_to_ranges(probs, threshold=0.5) == [(0, 2), (3, 19)]


def test_probs_to_ranges_all_below_threshold():
    assert probs_to_ranges([0.0] * 10, threshold=0.5) == [(0, 9)]


def test_enforce_min_len_keeps_leading_short_scene():
    # la prima scena non ha una precedente in cui fondersi: resta com'è
    scenes = scenes_from_ranges([(0, 3), (4, 40)], fps=24.0)
    merged = enforce_min_len(scenes, min_len=15)
    assert [(s.start_frame, s.end_frame) for s in merged] == [(0, 3), (4, 40)]


def test_enforce_min_len_empty():
    assert enforce_min_len([], min_len=15) == []
