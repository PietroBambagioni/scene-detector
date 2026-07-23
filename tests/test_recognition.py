import numpy as np

from scene_detector.recognition.identify import (
    average_embeddings,
    build_cast,
    centroids_of,
    cluster_faces,
    cluster_two_stage,
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


# ------------------------------------------- clustering a due stadi (4.4) ---

def test_within_shot_must_not_link_stesso_frame():
    # due volti quasi identici ma nello stesso frame: sono due persone, non una
    a = _blob(1, 1)
    quasi = a + 0.001 * np.ones_like(a)
    quasi /= np.linalg.norm(quasi, axis=1, keepdims=True)
    emb = np.vstack([a, quasi])
    labels = cluster_faces(emb, threshold=0.5, frame_indices=[0, 0])
    assert labels[0] != labels[1]


def test_within_shot_unisce_frame_diversi():
    # la stessa persona vista in tre frame diversi dello shot: un gruppo solo
    emb = _blob(2, 3)
    labels = cluster_faces(emb, threshold=0.5, frame_indices=[0, 1, 2])
    assert len(set(labels)) == 1


def test_within_shot_due_persone_su_piu_frame():
    # campo/controcampo: A e B compaiono insieme in 3 frame -> 2 gruppi, non 1 ne' 6
    a, b = _blob(3, 3), _blob(4, 3)
    emb = np.vstack([a[0], b[0], a[1], b[1], a[2], b[2]])
    labels = cluster_faces(emb, threshold=0.5, frame_indices=[0, 0, 1, 1, 2, 2])
    assert len(set(labels)) == 2
    assert labels[0] == labels[2] == labels[4]      # A resta A attraverso i frame
    assert labels[1] == labels[3] == labels[5]


def test_average_embeddings_normalizza_e_conta():
    emb = np.vstack([_blob(5, 2), _blob(6, 3)])
    means, ids, sizes = average_embeddings(emb, [0, 0, 1, 1, 1])
    assert ids == [0, 1] and sizes == [2, 3]
    assert np.allclose(np.linalg.norm(means, axis=1), 1.0)


def test_average_embeddings_ignora_i_non_assegnati():
    emb = _blob(7, 3)
    means, ids, sizes = average_embeddings(emb, [-1, 0, 0])
    assert ids == [0] and sizes == [2]


def test_two_stage_riconosce_la_stessa_persona_fra_shot():
    # la stessa identità in 3 shot, 2 volti per shot: un cluster solo
    emb = _blob(8, 6)
    labels = cluster_two_stage(emb, shot_indices=[0, 0, 1, 1, 2, 2],
                               frame_indices=[0, 1, 0, 1, 0, 1], threshold=0.5)
    assert len(set(labels)) == 1


def test_two_stage_tiene_separate_due_identita():
    a, b = _blob(9, 4), _blob(10, 4)
    emb = np.vstack([a[0], b[0], a[1], b[1], a[2], b[2], a[3], b[3]])
    labels = cluster_two_stage(emb, shot_indices=[0, 0, 0, 0, 1, 1, 1, 1],
                               frame_indices=[0, 0, 1, 1, 0, 0, 1, 1], threshold=0.5)
    assert len(set(labels)) == 2
    assert labels[0] == labels[2] == labels[4] == labels[6]


def test_two_stage_interfaccia_compatibile_con_cluster_faces():
    # una etichetta per volto in ingresso, come cluster_faces: build_cast non cambia
    emb = _blob(11, 5)
    labels = cluster_two_stage(emb, [0] * 5, list(range(5)))
    assert len(labels) == 5 and all(l >= 0 for l in labels)


def test_two_stage_vuoto():
    assert len(cluster_two_stage(np.zeros((0, 64)), [], [])) == 0
