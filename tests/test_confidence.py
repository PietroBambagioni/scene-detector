from scene_detector.confidence import reconcile
from scene_detector.scene import scenes_from_ranges


def test_reconcile_agreement():
    a = scenes_from_ranges([(0, 99), (100, 199), (200, 299)], 24.0)
    b = scenes_from_ranges([(0, 99), (100, 199), (200, 299)], 24.0)
    scenes, flags = reconcile(a, b, 300, 24.0, tol=5)
    assert flags == []
    assert len(scenes) == 3
    assert all(s.confidence == 1.0 for s in scenes)


def test_reconcile_within_tolerance():
    a = scenes_from_ranges([(0, 99), (100, 299)], 24.0)   # boundary 100
    b = scenes_from_ranges([(0, 102), (103, 299)], 24.0)  # boundary 103, |103-100|<=5
    scenes, flags = reconcile(a, b, 300, 24.0, tol=5)
    assert flags == []
    assert len(scenes) == 2


def test_reconcile_disagreement():
    a = scenes_from_ranges([(0, 99), (100, 199), (200, 299)], 24.0)  # boundary 100, 200
    b = scenes_from_ranges([(0, 99), (100, 299)], 24.0)             # boundary 100 solo
    scenes, flags = reconcile(a, b, 300, 24.0, tol=5)
    assert flags == [200]  # 200 presente solo in a
