from pathlib import Path

from scene_detector.catalog.manifest import build_manifest
from scene_detector.core.scene import scenes_from_ranges
from scene_detector.io.video import VideoInfo


def _info():
    return VideoInfo(path=Path("/film/Rogue.One.mp4"), fps=25.0, n_frames=200,
                     duration=8.0, width=1280, height=536)


def _scenes():
    return scenes_from_ranges([(0, 99), (100, 199)], fps=25.0, source="transnet")


def test_manifest_con_clip():
    m = build_manifest(_info(), _scenes(), "transnet")
    assert [s["clip"] for s in m["shots"]] == ["scene-001.mp4", "scene-002.mp4"]
    assert "video_src" not in m           # con le clip la UI non ha bisogno del film originale


def test_manifest_senza_clip():
    # --split-mode none: niente file su disco, la UI usa i media fragments sul film
    m = build_manifest(_info(), _scenes(), "transnet",
                       clip_template=None, video_src="../../Film/Rogue.One.mp4")
    assert [s["clip"] for s in m["shots"]] == [None, None]
    assert m["video_src"] == "../../Film/Rogue.One.mp4"
    assert m["video"] == "Rogue.One.mp4"  # il nome resta, cambia solo come lo si raggiunge


def test_manifest_tempi_invariati_senza_clip():
    # il taglio saltato non deve toccare i timecode: sono ciò che la UI usa per riprodurre
    con = build_manifest(_info(), _scenes(), "transnet")
    senza = build_manifest(_info(), _scenes(), "transnet", clip_template=None, video_src="x.mp4")
    for a, b in zip(con["shots"], senza["shots"]):
        assert (a["start_time"], a["end_time"]) == (b["start_time"], b["end_time"])


def test_merge_prior_recupera_i_campi_costosi(tmp_path):
    """Un run senza `--vlm`/`--asr` ricostruisce il manifest da zero: senza il recupero,
    descrizioni e dialoghi tornano a None e ore di calcolo sono perse (è già successo su
    *Rogue One*: 3204 descrizioni e 897 dialoghi)."""
    from scene_detector.catalog.manifest import merge_prior, write_manifest

    path = tmp_path / "manifest.json"
    write_manifest({"shots": [
        {"index": 0, "description": "un uomo cammina", "dialogue": "ciao", "characters": [3],
         "speakers": [1]},
        {"index": 1, "description": "un campo lungo", "dialogue": None, "characters": [],
         "speakers": []},
    ]}, path)

    nuovo = {"shots": [{"index": i, "description": None, "dialogue": None, "characters": [],
                        "speakers": []} for i in range(3)]}
    assert merge_prior(nuovo, path) == 2
    assert nuovo["shots"][0]["description"] == "un uomo cammina"
    assert nuovo["shots"][0]["dialogue"] == "ciao"
    assert nuovo["shots"][0]["characters"] == [3]
    assert nuovo["shots"][1]["description"] == "un campo lungo"
    assert nuovo["shots"][2]["description"] is None      # shot nuovo: niente da recuperare


def test_merge_prior_non_sovrascrive_il_calcolo_nuovo(tmp_path):
    from scene_detector.catalog.manifest import merge_prior, write_manifest

    path = tmp_path / "manifest.json"
    write_manifest({"shots": [{"index": 0, "description": "vecchia"}]}, path)
    nuovo = {"shots": [{"index": 0, "description": "appena calcolata"}]}
    assert merge_prior(nuovo, path) == 0
    assert nuovo["shots"][0]["description"] == "appena calcolata"


def test_merge_prior_primo_run_non_e_un_errore(tmp_path):
    from scene_detector.catalog.manifest import merge_prior

    assert merge_prior({"shots": [{"index": 0}]}, tmp_path / "assente.json") == 0
