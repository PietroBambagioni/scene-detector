import json

from scene_detector.catalog.thumbs import extract_thumbs
from scene_detector.catalog.ui import build_html


def _manifest(n=6, scenes=None):
    m = {
        "video": "Film.mp4", "fps": 25.0, "n_frames": n * 10, "duration": n * 0.4,
        "detector": "transnet", "n_shots": n, "cast": [],
        "shots": [{"index": i, "start_frame": i * 10, "end_frame": i * 10 + 9,
                   "start_time": i * 0.4, "end_time": (i + 1) * 0.4,
                   "clip": f"scene-{i+1:03d}.mp4", "confidence": 1.0,
                   "description": None, "dialogue": None, "characters": []}
                  for i in range(n)],
    }
    if scenes is not None:
        m["n_scenes"] = len(scenes)
        m["scenes"] = scenes
        for s in m["shots"]:
            s["thumb"] = f"thumbs/{s['index']:06d}.jpg"
    return m


def test_html_senza_scene_resta_a_due_livelli():
    """`--scenes` è opt-in: senza la chiave la pagina non deve accennare alle scene."""
    html = build_html(_manifest())
    assert "__DATA__" not in html
    assert '"scenes"' not in json.dumps(json.loads(html.split("const DATA = ")[1].split(";\n")[0]))
    assert "Scena " not in html.split("<script>")[1].split("const DATA")[0]


def test_html_con_scene_espone_i_dati():
    scenes = [{"index": 0, "first_shot": 0, "last_shot": 2, "start_frame": 0, "end_frame": 29,
               "start_time": 0.0, "end_time": 1.2},
              {"index": 1, "first_shot": 3, "last_shot": 5, "start_frame": 30, "end_frame": 59,
               "start_time": 1.2, "end_time": 2.4}]
    html = build_html(_manifest(scenes=scenes))
    data = json.loads(html.split("const DATA = ")[1].split(";\n")[0])
    assert data["n_scenes"] == 2
    assert data["scenes"][1]["first_shot"] == 3
    assert data["shots"][3]["thumb"] == "thumbs/000003.jpg"


def test_html_ha_i_pezzi_del_terzo_livello():
    """I marcatori che la UI a tre livelli usa: bande, intestazioni, unisci/dividi."""
    html = build_html(_manifest())
    for token in ('id="bands"', ".scene.open .shots", "mergeWithPrev", "splitAt", "checkScenes",
                  "playScene", "sceneOf"):
        assert token in html, token


def test_extract_thumbs_scrive_e_e_idempotente(tmp_path, monkeypatch):
    from scene_detector.catalog import thumbs as mod

    class _Img:
        saved = []

        def save(self, path, quality=None):
            _Img.saved.append(path)
            path.write_bytes(b"jpg")

    calls = []
    monkeypatch.setattr(mod, "sample_frames", lambda *a, **k: [_Img()], raising=False)
    monkeypatch.setattr("scene_detector.captioning.caption.sample_frames",
                        lambda *a, **k: (calls.append(a), [_Img()])[1])

    m = _manifest(3)
    n = extract_thumbs(m, "Film.mp4", tmp_path, progress=False)
    assert n == 3
    assert [s["thumb"] for s in m["shots"]] == [f"thumbs/{i:06d}.jpg" for i in range(3)]
    assert (tmp_path / "thumbs" / "000000.jpg").exists()
    # `fps` viene passato: senza, sugli shot corti si campiona il frame dello shot successivo
    assert calls[0][5] == 25.0

    n2 = extract_thumbs(m, "Film.mp4", tmp_path, progress=False)
    assert n2 == 0                      # file già su disco: nessuna estrazione in più
