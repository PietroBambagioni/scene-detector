"""`--from-manifest`: i confini corretti a mano nella UI al posto del detector."""
import json
from pathlib import Path

import pytest

from scene_detector.io.video import VideoInfo
from scene_detector.pipeline import _shots_corretti


def _info(n_frames=250, fps=25.0):
    return VideoInfo(path=Path("/film/banco.mp4"), fps=fps, n_frames=n_frames,
                     duration=n_frames / fps, width=640, height=360)


def _manifest(tmp_path, ranges, fps=25.0, **extra):
    m = {"video": "banco.mp4", "fps": fps, "n_frames": 250,
         "shots": [{"index": i, "start_frame": a, "end_frame": b}
                   for i, (a, b) in enumerate(ranges)],
         **extra}
    path = tmp_path / "corretto.json"
    path.write_text(json.dumps(m), encoding="utf-8")
    return path


def test_manifest_valido_passa(tmp_path):
    path = _manifest(tmp_path, [(0, 99), (100, 136), (137, 249)])
    assert len(_shots_corretti(path, _info())["shots"]) == 3


def test_film_sbagliato(tmp_path):
    """Il caso che fa piu' danno: taglia tutto nei punti sbagliati e non lo dice."""
    path = _manifest(tmp_path, [(0, 249)], fps=23.976)
    with pytest.raises(ValueError, match="altro film"):
        _shots_corretti(path, _info())


def test_buco_fra_gli_shot(tmp_path):
    # `end_frame` e' inclusivo: dopo 99 deve venire 100, non 101
    path = _manifest(tmp_path, [(0, 99), (101, 249)])
    with pytest.raises(ValueError, match="non contigui"):
        _shots_corretti(path, _info())


def test_sovrapposizione(tmp_path):
    path = _manifest(tmp_path, [(0, 99), (99, 249)])
    with pytest.raises(ValueError, match="non contigui"):
        _shots_corretti(path, _info())


def test_range_oltre_la_fine_del_video(tmp_path):
    path = _manifest(tmp_path, [(0, 99), (100, 400)])
    with pytest.raises(ValueError, match="escono dal video"):
        _shots_corretti(path, _info())


def test_non_parte_da_zero(tmp_path):
    path = _manifest(tmp_path, [(10, 249)])
    with pytest.raises(ValueError, match="escono dal video"):
        _shots_corretti(path, _info())


def test_manifest_vuoto(tmp_path):
    path = _manifest(tmp_path, [])
    with pytest.raises(ValueError, match="nessuno shot"):
        _shots_corretti(path, _info())


def test_le_clip_in_eccesso_diventano_orfane(tmp_path, monkeypatch):
    """Unire due shot lascia una clip di troppo: nome legittimo, contenuto ormai dentro un'altra.
    Rinominata e non cancellata — e il confronto e' sul numero, perche' sopra i 999 shot i nomi
    passano a 4 cifre e in ordine lessicografico `scene-1000` viene prima di `scene-999`."""
    from scene_detector.core.scene import scenes_from_ranges
    from scene_detector.segmentation import splitter

    monkeypatch.setattr(splitter.subprocess, "run", lambda *a, **k: None)
    for nome in ("scene-001.mp4", "scene-002.mp4", "scene-003.mp4", "scene-1000.mp4",
                 "scene-finale.mp4"):
        (tmp_path / nome).write_bytes(b"x")

    scenes = scenes_from_ranges([(0, 99), (100, 249)], 25.0)
    assert splitter.split(_info(), scenes, tmp_path, jobs=1) == 2      # la 003 e la 1000

    resta = sorted(p.name for p in tmp_path.iterdir())
    assert resta == ["scene-001.mp4", "scene-002.mp4", "scene-003.mp4.orfano",
                     "scene-1000.mp4.orfano", "scene-finale.mp4"]      # nulla e' stato cancellato


def test_i_confini_manuali_diventano_scene_senza_min_len(tmp_path):
    """Uno shot da 3 frame scelto a mano deve sopravvivere: `enforce_min_len` lo fonderebbe."""
    from scene_detector.core.scene import enforce_min_len, scenes_from_ranges

    ranges = [(0, 99), (100, 102), (103, 249)]
    scenes = scenes_from_ranges(ranges, 25.0, source="manuale")
    assert [(s.start_frame, s.end_frame) for s in scenes] == ranges
    # controprova: la fusione cieca del run normale se lo mangerebbe
    assert len(enforce_min_len(scenes, 5)) == 2


def test_from_manifest_non_taglia_sui_keyframe(tmp_path, monkeypatch):
    """`copy` snappa al keyframe precedente: il confine corretto a mano scivola di ~1 GOP.

    E' l'unico modo in cui `--from-manifest` puo' fallire senza dirlo — i frame nel manifest
    sono giusti, il taglio no.
    """
    from typer.testing import CliRunner

    from scene_detector import cli
    from scene_detector.core.config import SplitMode

    video = tmp_path / "banco.mp4"
    video.write_bytes(b"")
    corretto = _manifest(tmp_path, [(0, 249)])
    visti = []
    monkeypatch.setattr(cli.pipeline, "run", lambda cfg: visti.append(cfg))

    def invoca(*extra):
        r = CliRunner().invoke(cli.app, [str(video), "--from-manifest", str(corretto),
                                         "-o", str(tmp_path), *extra])
        assert r.exit_code == 0, r.output
        return visti.pop().split_mode

    assert invoca() is SplitMode.reencode
    assert invoca("--split-mode", "copy") is SplitMode.reencode
    assert invoca("--split-mode", "none") is SplitMode.none      # "non tagliare" resta tale


def test_il_ritaglio_conserva_confidenza_e_transizione(tmp_path):
    """Ripartiva tutto da `confidence=1.0` senza transizioni: dopo il primo ritaglio la coda di
    revisione era vuota e il manifest dava per certo ogni confine."""
    from scene_detector.pipeline import _scene_corrette

    path = _manifest(tmp_path, [(0, 99), (100, 136), (137, 249)])
    m = json.loads(path.read_text())
    m["shots"][1].update(confidence=0.12,
                         transition={"start_frame": 96, "end_frame": 99, "n_frames": 4})
    m["shots"][2]["confidence"] = None            # tagliato a mano nella UI
    scenes = _scene_corrette(m, 25.0)
    assert [s.confidence for s in scenes] == [1.0, 0.12, None]
    assert [s.transition for s in scenes] == [None, (96, 99), None]
