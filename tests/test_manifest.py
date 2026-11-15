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
    # sottocartella: il catalogo tiene le clip separate da manifest, miniature e index.html
    assert [s["clip"] for s in m["shots"]] == ["clip/scene-001.mp4", "clip/scene-002.mp4"]
    assert "video_src" not in m           # non passato: la chiave non compare (la pipeline lo passa sempre)


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
        {"index": 0, "start_frame": 0, "end_frame": 99, "description": "un uomo cammina", "dialogue": "ciao",
         "characters": [3], "speakers": [1]},
        {"index": 1, "start_frame": 100, "end_frame": 199, "description": "un campo lungo", "dialogue": None,
         "characters": [], "speakers": []},
    ]}, path)

    nuovo = {"shots": [{"index": i, "start_frame": i * 100, "end_frame": i * 100 + 99, "description": None, "dialogue": None,
                        "characters": [], "speakers": []} for i in range(3)]}
    assert merge_prior(nuovo, path) == 2
    assert nuovo["shots"][0]["description"] == "un uomo cammina"
    assert nuovo["shots"][0]["dialogue"] == "ciao"
    assert nuovo["shots"][0]["characters"] == [3]
    assert nuovo["shots"][1]["description"] == "un campo lungo"
    assert nuovo["shots"][2]["description"] is None      # shot nuovo: niente da recuperare


def test_merge_prior_non_sovrascrive_il_calcolo_nuovo(tmp_path):
    from scene_detector.catalog.manifest import merge_prior, write_manifest

    path = tmp_path / "manifest.json"
    write_manifest({"shots": [{"index": 0, "start_frame": 0, "end_frame": 9, "description": "vecchia"}]}, path)
    nuovo = {"shots": [{"index": 0, "start_frame": 0, "end_frame": 9, "description": "appena calcolata"}]}
    assert merge_prior(nuovo, path) == 0
    assert nuovo["shots"][0]["description"] == "appena calcolata"


def test_merge_prior_accoppia_per_range_non_per_indice(tmp_path):
    """Un taglio manuale nella UI sposta di uno tutti gli indici a valle. Accoppiando per `index`
    le descrizioni scivolerebbero sullo shot sbagliato: un danno silenzioso, peggio di perderle."""
    from scene_detector.catalog.manifest import merge_prior, write_manifest

    path = tmp_path / "manifest.json"
    write_manifest({"shots": [
        {"index": 0, "start_frame": 0, "end_frame": 99, "description": "una nave da guerra"},
        {"index": 1, "start_frame": 100, "end_frame": 199, "description": "un pianeta desertico"},
    ]}, path)

    # lo shot [0, 99] e' stato spezzato a 50: gli indici scalano, i range a valle no. Nessuna
    # delle due meta' e' lo shot che la descrizione racconta, e nessuna la riceve.
    nuovo = {"shots": [
        {"index": 0, "start_frame": 0, "end_frame": 49, "description": None},
        {"index": 1, "start_frame": 50, "end_frame": 99, "description": None},
        {"index": 2, "start_frame": 100, "end_frame": 199, "description": None},
    ]}
    assert merge_prior(nuovo, path) == 1
    assert [s["description"] for s in nuovo["shots"]] == [None, None, "un pianeta desertico"]


def test_merge_prior_non_recupera_su_un_confine_spostato(tmp_path):
    """Se lo shot inizia altrove non e' piu' lo stesso pezzo di film: non recuperare e' la scelta
    giusta, e il conteggio deve dirlo."""
    from scene_detector.catalog.manifest import merge_prior, write_manifest

    path = tmp_path / "manifest.json"
    write_manifest({"shots": [{"index": 0, "start_frame": 100, "end_frame": 199,
                               "description": "vecchia"}]}, path)
    nuovo = {"shots": [{"index": 0, "start_frame": 103, "end_frame": 199, "description": None}]}
    assert merge_prior(nuovo, path) == 0
    assert nuovo["shots"][0]["description"] is None


def test_merge_prior_non_recupera_se_si_sposta_la_fine(tmp_path):
    """Stesso inizio, fine diversa: con una soglia nuova [100, 199] diventa [100, 349] e la
    descrizione della sola prima meta' finiva sullo shot intero (su *Anna* 281 shot su 307)."""
    from scene_detector.catalog.manifest import merge_prior, write_manifest

    path = tmp_path / "manifest.json"
    write_manifest({"shots": [{"start_frame": 100, "end_frame": 199, "description": "vecchia",
                               "rivisto": True}]}, path)
    nuovo = {"shots": [{"start_frame": 100, "end_frame": 349, "description": None}]}
    assert merge_prior(nuovo, path) == 1                 # recupera solo il segno di rivisto
    assert nuovo["shots"][0]["description"] is None
    assert nuovo["shots"][0]["rivisto"] is True          # il confine d'apertura e' lo stesso


def test_merge_prior_primo_run_non_e_un_errore(tmp_path):
    from scene_detector.catalog.manifest import merge_prior

    assert merge_prior({"shots": [{"index": 0}]}, tmp_path / "assente.json") == 0


def test_i_nomi_delle_scene_sopravvivono_al_raggruppamento(tmp_path):
    """Un run con `--scenes` rifa' i gruppi da zero: senza il recupero il nome dura un run."""
    from scene_detector.catalog.manifest import merge_scene_names, write_manifest

    path = tmp_path / "manifest.json"
    write_manifest({"scenes": [{"start_frame": 0, "name": "Il cortile"},
                               {"start_frame": 300, "name": "La cena"}]}, path)

    # stesso confine -> il nome torna; confine spostato -> non torna, e va bene cosi'
    nuovo = {"scenes": [{"start_frame": 0}, {"start_frame": 305}]}
    assert merge_scene_names(nuovo, path) == 1
    assert nuovo["scenes"][0]["name"] == "Il cortile"
    assert "name" not in nuovo["scenes"][1]

    # un nome gia' presente non viene sovrascritto, e senza scene non succede niente
    tenuto = {"scenes": [{"start_frame": 0, "name": "Altro"}]}
    assert merge_scene_names(tenuto, path) == 0
    assert tenuto["scenes"][0]["name"] == "Altro"
    assert merge_scene_names({}, path) == 0


def test_il_segno_di_rivisto_sopravvive_al_run_dopo(tmp_path):
    """`rivisto` non costa GPU, costa ore di persona: perderlo vuol dire rivedere la coda."""
    from scene_detector.catalog.manifest import merge_prior, write_manifest

    path = tmp_path / "manifest.json"
    write_manifest({"shots": [{"start_frame": 0, "rivisto": True},
                              {"start_frame": 300, "rivisto": True}]}, path)

    # stesso confine -> il segno torna; confine spostato -> no, ed e' giusto: e' un altro taglio
    nuovo = {"shots": [{"start_frame": 0}, {"start_frame": 305}]}
    assert merge_prior(nuovo, path) == 1
    assert nuovo["shots"][0]["rivisto"] is True
    assert "rivisto" not in nuovo["shots"][1]


def test_write_manifest_non_lascia_un_file_a_meta(tmp_path, monkeypatch):
    """Se la scrittura si interrompe, su disco resta il manifest di prima, intero."""
    import pytest

    from scene_detector.catalog import manifest as mod

    path = tmp_path / "manifest.json"
    mod.write_manifest({"shots": [{"description": "vecchia"}]}, path)

    def interrotto(*a, **k):
        raise KeyboardInterrupt
    monkeypatch.setattr(mod.os, "replace", interrotto)
    with pytest.raises(KeyboardInterrupt):
        mod.write_manifest({"shots": [{"description": "nuova"}]}, path)
    assert mod.load_manifest(path)["shots"][0]["description"] == "vecchia"


def test_un_run_senza_faces_non_azzera_cast_e_scene(tmp_path):
    """`build_manifest` riparte da `cast: []`: un `--vlm` da solo lasciava negli shot gli id di
    personaggi che non esistevano piu' (su *Anna*: 29 personaggi e 35 scene azzerati)."""
    from scene_detector.catalog.manifest import load_prior, merge_film_keys, write_manifest

    path = tmp_path / "manifest.json"
    prima = build_manifest(_info(), _scenes(), "transnet")
    prima.update(cast=[{"id": 3, "name": "Anna"}], n_speakers=2, n_scenes=1,
                 scenes=[{"index": 0, "first_shot": 0, "last_shot": 1}])
    write_manifest(prima, path)

    nuovo = build_manifest(_info(), _scenes(), "transnet")
    assert merge_film_keys(nuovo, load_prior(path)) == ["cast", "scenes", "n_scenes", "n_speakers"]
    assert nuovo["cast"] == [{"id": 3, "name": "Anna"}]
    assert nuovo["scenes"][0]["last_shot"] == 1

    # lo step vero ha gia' scritto: non si copre
    rifatto = build_manifest(_info(), _scenes(), "transnet")
    rifatto["cast"] = [{"id": 0, "name": "Personaggio 1"}]
    assert "cast" not in merge_film_keys(rifatto, load_prior(path))
    assert rifatto["cast"][0]["name"] == "Personaggio 1"


def test_cast_e_scene_non_tornano_se_i_confini_si_sono_mossi(tmp_path):
    """Le scene puntano agli shot per indice: su shot diversi indicherebbero un altro pezzo di
    film. Basta un confine spostato, anche solo la fine dell'ultimo shot."""
    from scene_detector.catalog.manifest import load_prior, merge_film_keys, write_manifest

    path = tmp_path / "manifest.json"
    prima = build_manifest(_info(), _scenes(), "transnet")
    prima.update(cast=[{"id": 3, "name": "Anna"}], scenes=[{"first_shot": 0, "last_shot": 1}])
    write_manifest(prima, path)

    for ranges in ([(0, 89), (90, 199)], [(0, 99), (100, 198)], [(0, 199)]):
        nuovo = build_manifest(_info(), scenes_from_ranges(ranges, 25.0), "transnet")
        assert merge_film_keys(nuovo, load_prior(path)) == []
        assert nuovo["cast"] == [] and "scenes" not in nuovo

    # primo run, o manifest troncato da un'interruzione: non e' un errore
    assert load_prior(tmp_path / "assente.json") is None
    (tmp_path / "rotto.json").write_text("{", encoding="utf-8")
    assert load_prior(tmp_path / "rotto.json") is None
    assert merge_film_keys(build_manifest(_info(), _scenes(), "transnet"), None) == []
