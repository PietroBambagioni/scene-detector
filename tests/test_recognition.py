import numpy as np

from scene_detector.recognition.identify import (
    build_cast,
    centroids_of,
    cluster_faces,
    match_gallery,
)


def _blob(seed, n, dim=64, spread=0.03):
    """n embedding normalizzati stretti attorno a un centro casuale (una 'identità')."""
    rng = np.random.default_rng(seed)
    center = rng.normal(size=dim)
    center /= np.linalg.norm(center)
    v = center + spread * rng.normal(size=(n, dim))
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def test_cluster_separates_distinct_identities():
    a, b, c = _blob(1, 5), _blob(2, 5), _blob(3, 5)
    labels = cluster_faces(np.vstack([a, b, c]), threshold=0.5)
    assert len(set(labels)) == 3
    # ogni blob resta compatto in un unico cluster
    assert len(set(labels[:5])) == 1
    assert len(set(labels[5:10])) == 1
    assert len(set(labels[10:])) == 1


def test_cluster_empty_returns_empty():
    assert list(cluster_faces(np.zeros((0, 8)))) == []


def test_cluster_det_score_order_is_stable():
    emb = np.vstack([_blob(1, 4), _blob(2, 4)])
    scores = np.linspace(0.9, 0.5, len(emb))
    labels = cluster_faces(emb, threshold=0.5, det_scores=scores)
    assert len(set(labels)) == 2


def test_match_gallery_assigns_distinct_names():
    a, b = _blob(1, 4), _blob(2, 4)
    emb = np.vstack([a, b])
    labels = cluster_faces(emb, 0.5)
    cents = centroids_of(emb, labels)
    gallery = {
        "Alice": a.mean(0) / np.linalg.norm(a.mean(0)),
        "Bob": b.mean(0) / np.linalg.norm(b.mean(0)),
    }
    names = match_gallery(cents, gallery, threshold=0.5)
    assert set(names.values()) == {"Alice", "Bob"}
    assert len(names) == 2  # matching 1-a-1, nessun nome riusato


def test_match_gallery_empty_gallery():
    assert match_gallery({0: np.ones(4)}, {}, 0.5) == {}


def test_match_gallery_below_threshold_no_match():
    # centroide ortogonale al volto in gallery -> nessun match
    cents = {0: np.array([1.0, 0.0, 0.0, 0.0])}
    gallery = {"X": np.array([0.0, 1.0, 0.0, 0.0])}
    assert match_gallery(cents, gallery, threshold=0.5) == {}


def test_build_cast_counts_shots_and_faces():
    labels = np.array([0, 0, 1, 0, 1])
    shots = [0, 1, 1, 2, 3]
    cast, per_shot = build_cast(labels, shots)
    by_id = {c["id"]: c for c in cast}
    assert by_id[0]["n_faces"] == 3 and by_id[0]["n_shots"] == 3  # shot {0,1,2}
    assert by_id[1]["n_faces"] == 2 and by_id[1]["n_shots"] == 2  # shot {1,3}
    assert by_id[0]["name"] == "Personaggio 1"  # anonimo, id+1
    assert per_shot[1] == {0, 1}                  # shot 1 ha entrambi i personaggi
    assert cast[0]["id"] == 0                     # ordinato per n_shots desc


def test_build_cast_gallery_names_and_min_faces():
    labels = np.array([0, 0, 1])
    shots = [0, 1, 2]
    cast, per_shot = build_cast(labels, shots, names={0: "Alice"}, min_faces=2)
    assert [c["id"] for c in cast] == [0]     # cluster 1 (1 volto) scartato da min_faces
    assert cast[0]["name"] == "Alice"         # nome reale dalla gallery
    assert 2 not in per_shot                  # lo shot del cluster scartato non compare
