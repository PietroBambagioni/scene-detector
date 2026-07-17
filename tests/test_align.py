from scene_detector.transcription.align import assign_dialogue


def test_assign_by_midpoint():
    shots = [
        {"start_time": 0.0, "end_time": 5.0, "dialogue": None},
        {"start_time": 5.0, "end_time": 10.0, "dialogue": None},
    ]
    segments = [
        {"start": 1.0, "end": 2.0, "text": "ciao"},       # mid 1.5 -> shot 0
        {"start": 4.5, "end": 6.0, "text": "come stai"},   # mid 5.25 -> shot 1
        {"start": 7.0, "end": 8.0, "text": "bene"},        # mid 7.5 -> shot 1
    ]
    assign_dialogue(shots, segments)
    assert shots[0]["dialogue"] == "ciao"
    assert shots[1]["dialogue"] == "come stai bene"


def test_tail_segment_goes_to_last_shot():
    shots = [{"start_time": 0.0, "end_time": 5.0, "dialogue": None}]
    assign_dialogue(shots, [{"start": 4.9, "end": 5.2, "text": "fine"}])  # mid 5.05 >= end
    assert shots[0]["dialogue"] == "fine"


def test_assign_empty():
    shots = [{"start_time": 0.0, "end_time": 5.0, "dialogue": None}]
    assign_dialogue(shots, [])
    assert shots[0]["dialogue"] is None


def test_assign_unordered_segments_and_multi_shot():
    shots = [
        {"start_time": 0.0, "end_time": 3.0, "dialogue": None},
        {"start_time": 3.0, "end_time": 6.0, "dialogue": None},
        {"start_time": 6.0, "end_time": 9.0, "dialogue": None},
    ]
    segments = [  # volutamente fuori ordine
        {"start": 7.0, "end": 8.0, "text": "c"},   # mid 7.5 -> shot 2
        {"start": 0.5, "end": 1.0, "text": "a"},   # mid 0.75 -> shot 0
        {"start": 3.5, "end": 4.5, "text": "b"},   # mid 4.0 -> shot 1
    ]
    assign_dialogue(shots, segments)
    assert [s["dialogue"] for s in shots] == ["a", "b", "c"]
