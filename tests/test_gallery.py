import json

from scene_detector.catalog.gallery import build_index_html, scan_catalogs


def _write_manifest(dir_path, video, n_shots, duration, detector):
    dir_path.mkdir(parents=True)
    (dir_path / "manifest.json").write_text(
        json.dumps({"video": video, "n_shots": n_shots, "duration": duration, "detector": detector}),
        encoding="utf-8",
    )


def test_scan_finds_catalogs_sorted(tmp_path):
    _write_manifest(tmp_path / "Bravo", "Bravo.mp4", 5, 120.0, "transnet")
    _write_manifest(tmp_path / "Anna", "Anna.mp4", 373, 12829.4, "ensemble")
    catalogs = scan_catalogs(tmp_path)
    assert [c["video"] for c in catalogs] == ["Anna.mp4", "Bravo.mp4"]
    assert catalogs[0]["dir"] == "Anna"
    assert catalogs[0]["n_shots"] == 373


def test_scan_ignores_dirs_without_manifest(tmp_path):
    _write_manifest(tmp_path / "Anna", "Anna.mp4", 5, 120.0, "transnet")
    (tmp_path / "empty").mkdir()          # nessun manifest → ignorata
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "manifest.json").write_text("{ not json", encoding="utf-8")
    catalogs = scan_catalogs(tmp_path)
    assert [c["dir"] for c in catalogs] == ["Anna"]


def test_build_index_html_is_self_contained(tmp_path):
    _write_manifest(tmp_path / "Anna", "Anna.mp4", 5, 120.0, "transnet")
    html = build_index_html(scan_catalogs(tmp_path))
    assert "<!doctype html>" in html
    assert "Anna.mp4" in html
    assert "__DATA__" not in html
    assert "http://" not in html and "https://" not in html   # nessuna dep esterna
