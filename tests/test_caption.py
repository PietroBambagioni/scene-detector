from scene_detector.captioning import caption
from scene_detector.captioning.caption import _timestamps, build_prompt, caption_manifest


def test_timestamps_within_range_and_ordered():
    ts = _timestamps(10.0, 20.0, 3)
    assert len(ts) == 3
    assert ts == sorted(ts)
    assert 10.0 < ts[0] and ts[-1] < 20.0   # rientrati per evitare i frame di taglio


def test_timestamps_single_is_midpoint():
    assert _timestamps(4.0, 8.0, 1) == [6.0]


def test_timestamps_non_superano_lultimo_frame():
    """Shot da 5 frame a 25 fps: il rientro del 15% (0,03 s) è meno di un frame (0,04 s).

    Senza il tetto `end - 1/fps` l'ultimo istante cade sul frame dello shot **successivo** — o su
    niente, se lo shot chiude il video.
    """
    start, fps = 100.0, 25.0
    end = start + 5 / fps            # end_frame + 1: esclusivo
    ts = _timestamps(start, end, 3, fps)
    assert max(ts) <= end - 1 / fps + 1e-9
    assert min(ts) >= start - 1e-9
    assert ts == sorted(ts)


def test_timestamps_shot_da_un_frame():
    """Caso degenere: un solo frame disponibile, tutti gli istanti ci cadono sopra."""
    assert _timestamps(10.0, 10.04, 3, 25.0) == [10.0, 10.0, 10.0]


def test_build_prompt_italian_and_dialogue():
    p = build_prompt(3, dialogue="Cosa fai qui?")
    assert "italiano" in p
    assert "3 fotogrammi" in p
    assert "Cosa fai qui?" in p


def test_build_prompt_dialogue_is_context_not_content():
    # il dialogo ha già un campo suo nel manifest: il VLM non deve parafrasarlo
    p = build_prompt(3, dialogue="Cosa fai qui?")
    assert "Non ripeterlo" in p


def test_build_prompt_singular_no_dialogue():
    p = build_prompt(1)
    assert "un fotogramma" in p
    assert "Dialogo" not in p


def test_build_prompt_with_characters():
    p = build_prompt(3, characters=["Marco", "Giulia"])
    assert "Personaggi riconosciuti" in p
    assert "Marco, Giulia" in p


class _StubCaptioner:
    def __init__(self):
        self.calls = 0
        self.last_characters = None

    def describe(self, frames, dialogue=None, characters=None):
        self.calls += 1
        self.last_characters = characters
        return f"descr {self.calls}"


def test_caption_manifest_skips_already_done(monkeypatch):
    # evita ffmpeg: sample_frames finto
    monkeypatch.setattr(caption, "sample_frames", lambda *a, **k: ["frame"])
    manifest = {"shots": [
        {"index": 0, "start_frame": 0, "end_frame": 50, "start_time": 0.0, "end_time": 2.0,
         "description": "GIA_FATTO", "dialogue": None},
        {"index": 1, "start_frame": 50, "end_frame": 100, "start_time": 2.0, "end_time": 4.0,
         "description": None, "dialogue": None},
    ]}
    cap = _StubCaptioner()
    caption_manifest(manifest, "video.mp4", cap, progress=False)
    assert cap.calls == 1                              # solo lo shot senza descrizione
    assert manifest["shots"][0]["description"] == "GIA_FATTO"
    assert manifest["shots"][1]["description"] == "descr 1"


def test_caption_manifest_esclude_i_cluster_incerti(monkeypatch):
    """Un cluster `uncertain` fonde personaggi diversi: il suo nome non entra nel prompt."""
    monkeypatch.setattr(caption, "sample_frames", lambda *a, **k: ["frame"])
    manifest = {
        "cast": [{"id": 0, "name": "Jyn"},
                 {"id": 1, "name": "Personaggio 23", "uncertain": True}],
        "shots": [{"index": 0, "start_frame": 0, "end_frame": 50, "start_time": 0.0,
                   "end_time": 2.0, "description": None, "dialogue": None,
                   "characters": [0, 1]}],
    }
    cap = _StubCaptioner()
    caption_manifest(manifest, "video.mp4", cap, progress=False)
    assert cap.last_characters == ["Jyn"]


class _FlakyCaptioner:
    def __init__(self, fail_on):
        self.fail_on = fail_on
        self.calls = 0

    def describe(self, frames, dialogue=None, characters=None):
        self.calls += 1
        if self.calls == self.fail_on:
            raise RuntimeError("boom")
        return f"descr {self.calls}"


def test_caption_manifest_resilient_per_shot(monkeypatch):
    monkeypatch.setattr(caption, "sample_frames", lambda *a, **k: ["frame"])
    manifest = {"shots": [
        {"index": 0, "start_frame": 0, "end_frame": 100, "start_time": 0.0, "end_time": 4.0,
         "description": None, "dialogue": None},
        {"index": 1, "start_frame": 100, "end_frame": 200, "start_time": 4.0, "end_time": 8.0,
         "description": None, "dialogue": None},
    ]}
    cap = _FlakyCaptioner(fail_on=1)   # esplode sul primo shot
    caption_manifest(manifest, "video.mp4", cap, progress=False)
    assert manifest["shots"][0]["description"] is None      # fallito: resta None (editabile in UI)
    assert manifest["shots"][1]["description"] == "descr 2"  # il batch prosegue


def test_caption_manifest_injects_character_names(monkeypatch):
    monkeypatch.setattr(caption, "sample_frames", lambda *a, **k: ["frame"])
    manifest = {
        "cast": [{"id": 0, "name": "Alice"}, {"id": 1, "name": "Bob"}],
        "shots": [
            {"index": 0, "start_frame": 0, "end_frame": 100, "start_time": 0.0, "end_time": 4.0,
             "description": None, "dialogue": None, "characters": [0, 1]},
        ],
    }
    cap = _StubCaptioner()
    caption_manifest(manifest, "video.mp4", cap, progress=False)
    assert cap.last_characters == ["Alice", "Bob"]   # id cluster risolti in nomi dal cast


def test_il_seek_non_scavalca_lo_shot_a_23_976_fps(monkeypatch):
    """ffmpeg con `-ss` consegna il primo frame con PTS >= t, e t viaggia arrotondato al ms.
    Chiesto sul PTS esatto dell'ultimo frame, a 23,976 fps l'arrotondamento lo supera una volta
    su due e torna il primo frame dello shot **dopo**. A 25 fps non succede mai (PTS multipli di
    40 ms): e' il motivo per cui ne' *Anna* ne' i banchi l'avevano mostrato."""
    fps = 24000 / 1001

    def frame_di_ffmpeg(t):
        t = float(f"{max(0.0, t):.3f}")                 # come lo formatta `_extract_frame`
        f = int(t * fps)
        return f if f / fps >= t - 1e-12 else f + 1     # primo frame con PTS >= t

    visti = []
    monkeypatch.setattr(caption, "_extract_frame", lambda video, t, size: visti.append(t))
    fuori = 0
    for start in range(1, 400):
        for lung, n in ((1, 1), (2, 1), (5, 3), (6, 3), (6, 6)):
            end = start + lung - 1                      # inclusivo
            visti.clear()
            # i tempi arrivano dal manifest, gia' arrotondati al millisecondo
            caption.sample_frames("f.mp4", round(start / fps, 3), round((end + 1) / fps, 3), n, 64, fps)
            fuori += any(not start <= frame_di_ffmpeg(t) <= end for t in visti)
    assert fuori == 0

    # controprova: senza il mezzo frame il difetto c'e', quindi il test lo sa vedere
    ultimo = [f / fps for f in range(1, 400)]           # seek sul PTS esatto del frame f
    assert sum(frame_di_ffmpeg(t) != f for f, t in enumerate(ultimo, 1)) > 100
