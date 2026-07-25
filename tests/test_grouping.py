import numpy as np

from scene_detector.core.scene import scenes_from_ranges
from scene_detector.grouping import (
    build_scene_entries,
    distance_matrix,
    estimate_scenes_count,
    group_shots,
    optimal_sequence,
    pool_by_shot,
    shot_signatures,
)

PALETTE = np.array([[200, 30, 30], [30, 200, 30], [30, 30, 200]], np.uint8)
PER_SHOT = 10


def _frames(pattern, size=4):
    """Frame sintetici 4x4: ogni shot un colore pieno, `pattern` dice quale."""
    blocks = [np.broadcast_to(PALETTE[p], (PER_SHOT, size, size, 3)) for p in pattern]
    return np.ascontiguousarray(np.concatenate(blocks))


def _shots(pattern, transitions=None, fps=25.0):
    ranges = [(i * PER_SHOT, i * PER_SHOT + PER_SHOT - 1) for i in range(len(pattern))]
    return scenes_from_ranges(ranges, fps, transitions=transitions)


def _sigs(pattern, dim=8, noise=0.01, seed=0):
    """Una firma per shot: istogrammi quasi one-hot, uno per 'palette'."""
    rng = np.random.default_rng(seed)
    v = np.eye(dim)[list(pattern)] + noise * rng.random((len(pattern), dim))
    return v / v.sum(1, keepdims=True)


def test_tre_blocchi_netti():
    D = distance_matrix(_sigs([0] * 5 + [1] * 5 + [2] * 5))
    assert optimal_sequence(D, 3) == [(0, 4), (5, 9), (10, 14)]


def test_campo_controcampo_resta_una_scena():
    """A-B-A-B-A-B è una scena sola: il metodo di copertura (manuale r. 1117)."""
    D = distance_matrix(_sigs([0, 1] * 3 + [2] * 6))
    assert optimal_sequence(D, 2) == [(0, 5), (6, 11)]


def test_montaggio_alternato_non_stima_una_scena_per_stacco():
    """Alternanza su tutta la sequenza (manuale r. 1583): pochi blocchi, non 16."""
    D = distance_matrix(_sigs([0, 1] * 8))
    assert estimate_scenes_count(D) <= 3


def test_stima_ritrova_i_tre_blocchi():
    D = distance_matrix(_sigs([0] * 6 + [1] * 6 + [2] * 6))
    assert estimate_scenes_count(D) == 3


def test_shot_signatures_separa_i_colori():
    """Il produttore HSV: due palette diverse devono dare firme lontane."""
    pattern = [0, 0, 0, 1, 1, 1]
    sigs = shot_signatures(_frames(pattern), _shots(pattern))
    assert sigs.shape == (6, 8 * 4 * 4)
    np.testing.assert_allclose(sigs.sum(1), 1.0)  # normalizzate L1
    D = distance_matrix(sigs)
    assert D[0, 1] < 0.01 < D[0, 3]


def test_group_shots_dalle_firme():
    pattern = [0, 0, 0, 1, 1, 1]
    groups = group_shots(_shots(pattern), shot_signatures(_frames(pattern), _shots(pattern)),
                         n_scenes=2)
    assert groups == [(0, 2), (3, 5)]


def test_le_transizioni_non_spezzano():
    """`transition` non è punteggiatura: 0/7 nell'annotazione cieca. Vedi `group_shots`."""
    pattern = [0] * 6
    trans = [None] * 6
    trans[3] = (22, 30)  # 9 frame, la fascia che sembrava "dissolvenza"
    shots = _shots(pattern, transitions=trans)
    assert group_shots(shots, _sigs(pattern), n_scenes=1) == [(0, 5)]


def test_pool_by_shot_media_i_frame_del_suo_shot():
    """3 frame per shot: ogni shot deve prendere i suoi, non quelli del vicino."""
    embs = np.array([[1.0, 0], [1.0, 0], [1.0, 0],      # shot 0
                     [0, 1.0], [0, 1.0], [0, 1.0],      # shot 1
                     [1.0, 0], [0, 1.0], [1.0, 0]])     # shot 2: media (2/3, 1/3)
    out = pool_by_shot(embs, [0, 0, 0, 1, 1, 1, 2, 2, 2], 3)
    np.testing.assert_allclose(np.linalg.norm(out, axis=1), 1.0)
    np.testing.assert_allclose(out[0], [1, 0])
    np.testing.assert_allclose(out[1], [0, 1])
    assert out[2][0] > out[2][1] > 0


def test_pool_by_shot_shot_senza_frame():
    """Uno shot senza frame campionati resta a zero, non divide per zero."""
    out = pool_by_shot(np.array([[1.0, 0], [0, 1.0]]), [0, 2], 3)
    np.testing.assert_allclose(out[1], [0, 0])


def test_scene_entries_hanno_gli_estremi_giusti():
    shots = _shots([0] * 6)
    entries = build_scene_entries([(0, 2), (3, 5)], shots)
    assert [e["index"] for e in entries] == [0, 1]
    assert entries[0] == {"index": 0, "first_shot": 0, "last_shot": 2,
                          "start_frame": 0, "end_frame": 29,
                          "start_time": 0.0, "end_time": 1.2}
    # contigui e senza buchi: end_frame + 1 == start_frame della successiva
    assert entries[0]["end_frame"] + 1 == entries[1]["start_frame"]


def test_meno_di_due_shot():
    assert group_shots([], np.zeros((0, 8))) == []
    assert group_shots(_shots([0]), _sigs([0])) == [(0, 0)]
