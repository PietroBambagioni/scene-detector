from scene_detector.core.scene import Scene, scenes_from_ranges, enforce_min_len
from scene_detector.detection.neural import (probs_to_ranges, boundary_confidences,
                                             runs_to_ranges)


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


# ------------------------------------------------------- runs_to_ranges -----

def test_runs_to_ranges_gradual_is_one_transition():
    """Una dissolvenza (frame caldi consecutivi) è UNA giunta, non una fila di tagli."""
    probs = [0.0] * 10 + [0.9] * 5 + [0.0] * 10          # corsa 10..14
    ranges, transitions = runs_to_ranges(probs, threshold=0.5)
    assert ranges == [(0, 14), (15, 24)]                  # contigui, coprono tutti i frame
    assert transitions == [None, (10, 14)]                # larghezza 5, sull'apertura del 2°


def test_runs_to_ranges_hard_cut_has_no_width():
    """Una corsa da un frame solo è uno stacco netto: nessuna larghezza da riportare."""
    probs = [0.0] * 10 + [0.9] + [0.0] * 9
    ranges, transitions = runs_to_ranges(probs, threshold=0.5)
    assert ranges == [(0, 10), (11, 19)]
    assert transitions == [None, None]


def test_runs_to_ranges_matches_probs_to_ranges_on_isolated_peaks():
    """Con picchi isolati il contratto coincide con quello di `probs_to_ranges`."""
    probs = [0.0] * 5 + [0.9] + [0.0] * 5 + [0.9] + [0.0] * 5
    ranges, _ = runs_to_ranges(probs, threshold=0.5)
    assert ranges == probs_to_ranges(probs, threshold=0.5)


def test_runs_to_ranges_all_below_threshold():
    ranges, transitions = runs_to_ranges([0.0] * 10, threshold=0.5)
    assert ranges == [(0, 9)] and transitions == [None]


def test_runs_to_ranges_run_at_end():
    """Corsa che tocca l'ultimo frame: nessuno shot vuoto in coda."""
    probs = [0.0] * 8 + [0.9] * 2
    ranges, transitions = runs_to_ranges(probs, threshold=0.5)
    assert ranges == [(0, 9)] and transitions == [None]


def test_scene_carries_transition_through_merge():
    """`enforce_min_len` fonde: sopravvive la giunta della scena che resta."""
    scenes = scenes_from_ranges([(0, 19), (20, 24), (25, 60)], fps=24.0,
                                transitions=[None, (18, 19), (23, 24)])
    out = enforce_min_len(scenes, 10)                     # la 2ª (5 frame) viene assorbita
    assert [(s.start_frame, s.end_frame) for s in out] == [(0, 24), (25, 60)]
    assert [s.transition for s in out] == [None, (23, 24)]


# ---------------------------------------------------------------- min_peak ---

def test_min_peak_scarta_le_corse_tiepide_e_tiene_le_calde():
    """Il picco decide se il taglio esiste; la soglia decide solo dove comincia e finisce."""
    probs = [0.0] * 30
    probs[10:14] = [0.1, 0.2, 0.15, 0.1]   # corsa larga ma tiepida: flicker
    probs[20:22] = [0.3, 0.9]              # corsa calda: taglio vero
    ranges, _ = runs_to_ranges(probs, threshold=0.05)
    assert len(ranges) == 3                # senza min_peak: due confini
    ranges, trans = runs_to_ranges(probs, threshold=0.05, min_peak=0.5)
    assert ranges == [(0, 21), (22, 29)]   # resta solo il confine caldo
    assert trans == [None, (20, 21)]       # e conserva la larghezza delimitata a 0,05


def test_min_peak_non_rompe_il_contratto_dei_range():
    """Contigui e copertura totale: è il contratto su cui poggiano splitter e confidenze."""
    import random
    rng = random.Random(0)
    probs = [rng.random() ** 3 for _ in range(200)]
    for mp in (0.0, 0.3, 0.5, 0.9, 1.1):
        ranges, trans = runs_to_ranges(probs, threshold=0.05, min_peak=mp)
        assert ranges[0][0] == 0 and ranges[-1][1] == len(probs) - 1
        assert all(b[0] == a[1] + 1 for a, b in zip(ranges, ranges[1:]))
        assert len(trans) == len(ranges)


def test_min_peak_zero_e_il_comportamento_di_prima():
    """Default spento: nessuna regressione sui cataloghi esistenti."""
    probs = [0.0, 0.9, 0.0, 0.1, 0.2, 0.0, 0.7, 0.0]
    assert runs_to_ranges(probs, 0.05, 0.0) == runs_to_ranges(probs, 0.05)


def test_cover_exactly_taglia_lo_sforo_del_decode():
    """ffmpeg decodifica 2 frame in più di `duration × fps`: l'ultimo shot non deve sforare.

    Senza questo, `_shots_corretti` rifiuta il manifest che la pipeline ha appena scritto e
    `--from-manifest` non funziona (era il caso di *Anna*: 320737 decodificati, 320735 da probe).
    """
    from scene_detector.detection.neural import cover_exactly
    ranges, trans = [(0, 9), (10, 19), (20, 21)], [None, (9, 9), (19, 20)]
    r, t = cover_exactly(ranges, trans, 20)
    assert r == [(0, 9), (10, 19)] and t == [None, (9, 9)]
    assert r[-1][1] == 19


def test_cover_exactly_allunga_se_il_decode_e_corto():
    """E vale al contrario: meno frame decodificati non devono lasciare un buco in coda."""
    from scene_detector.detection.neural import cover_exactly
    r, t = cover_exactly([(0, 9), (10, 15)], [None, (9, 9)], 20)
    assert r == [(0, 9), (10, 19)] and t == [None, (9, 9)]


def test_la_confidenza_di_una_graduale_e_il_picco_non_la_coda():
    """Una corsa larga finisce per costruzione su un frame appena sopra soglia: leggendo quello,
    ogni dissolvenza sembrava un confine dubbio (su *Anna* mediana 0,10 contro un picco di 0,675)."""
    probs = [0.0] * 40
    probs[10] = 0.95                                     # stacco netto: corsa da un frame
    probs[24:29] = [0.1, 0.4, 0.8, 0.3, 0.06]            # dissolvenza: corsa 24..28
    ranges, transitions = runs_to_ranges(probs, 0.05)
    assert ranges == [(0, 10), (11, 28), (29, 39)]
    assert boundary_confidences(ranges, probs, transitions) == [1.0, 0.95, 0.8]


def test_anche_pyscenedetect_copre_esattamente_i_frame_di_probe(monkeypatch):
    """OpenCV conta i frame per conto suo: l'invariante «coprono tutti i frame di probe» valeva
    solo sulla via neurale, e un manifest di PySceneDetect poteva non passare `--from-manifest`."""
    import sys
    from types import SimpleNamespace as NS

    from scene_detector.detection.pyscenedetect import PySceneDetectDetector

    tc = lambda f: NS(get_frames=lambda: f)
    falso = NS(open_video=lambda p: None, ContentDetector=lambda **k: None,
               SceneManager=lambda: NS(add_detector=lambda d: None,
                                       detect_scenes=lambda v, show_progress: None,
                                       # `end` esclusivo; OpenCV vede 203 frame, probe 200
                                       get_scene_list=lambda: [(tc(0), tc(100)), (tc(100), tc(203))]))
    monkeypatch.setitem(sys.modules, "scenedetect", falso)

    scenes = PySceneDetectDetector().detect(NS(path="f.mp4", n_frames=200, fps=25.0))
    assert [(s.start_frame, s.end_frame) for s in scenes] == [(0, 99), (100, 199)]
