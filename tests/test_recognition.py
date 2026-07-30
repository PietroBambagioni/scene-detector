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


def test_build_cast_gallery_names_and_min_shots():
    labels = np.array([0, 0, 1])
    shots = [0, 1, 2]
    cast, per_shot = build_cast(labels, shots, names={0: "Alice"}, min_shots=2)
    assert [c["id"] for c in cast] == [0]     # cluster 1 (1 shot solo) scartato da min_shots
    assert cast[0]["name"] == "Alice"         # nome reale dalla gallery
    assert 2 not in per_shot                  # lo shot del cluster scartato non compare


def test_build_cast_min_shots_counts_distinct_shots_not_faces():
    # stesso volto in 3 frame di UN solo shot: 3 volti ma 1 shot -> scartato da min_shots=2
    labels = np.array([0, 0, 0])
    shots = [5, 5, 5]
    cast, _ = build_cast(labels, shots, min_shots=2)
    assert cast == []                          # ricorre in 1 shot solo, non e' cast


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


def test_mark_uncertain_segna_i_cluster_non_volto():
    """det_score mediano basso = il rilevatore non lo dà per volto umano (droidi, elmetti)."""
    from scene_detector.recognition.faces import mark_uncertain

    cast = [{"id": 0, "name": "Jyn"}, {"id": 1, "name": "Personaggio 23"}]
    labels = np.array([0, 0, 0, 1, 1, 1])
    scores = np.array([0.82, 0.79, 0.86, 0.52, 0.58, 0.61])
    assert mark_uncertain(cast, labels, scores) == 1
    assert "uncertain" not in cast[0] and cast[0]["det_median"] == 0.82
    assert cast[1]["uncertain"] is True and cast[1]["det_median"] == 0.58


def test_mark_uncertain_non_segna_un_volto_debole_ma_valido():
    from scene_detector.recognition.faces import mark_uncertain

    cast = [{"id": 0, "name": "in penombra"}]
    assert mark_uncertain(cast, np.zeros(3, int), np.array([0.66, 0.70, 0.68])) == 0


# ----------------------------------------------- raffinamento dei cluster non-volto (4.5) ---

def test_split_by_reliability_divide_maestri_e_sospetti():
    """Sopra UNCERTAIN_DET ArcFace riconosce volti umani e insegna; sotto, va rimesso in gioco."""
    from scene_detector.recognition.faces import split_by_reliability

    labels = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
    scores = np.array([0.82, 0.79, 0.86, 0.52, 0.58, 0.61, 0.80, 0.81, 0.83])
    shots = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9])
    ids, sospetti = split_by_reliability(labels, scores, shots)
    assert sospetti == {1}
    assert list(ids) == [0, 0, 0, -1, -1, -1, 2, 2, 2]


def test_split_by_reliability_scarta_i_maestri_che_non_ricorrono():
    """Un cluster tutto dentro un paio di shot non ha visto abbastanza luci: non insegna nulla."""
    from scene_detector.recognition.faces import split_by_reliability

    labels = np.array([0, 0, 0, 1, 1, 1])
    scores = np.full(6, 0.8)
    shots = np.array([1, 1, 2, 7, 8, 9])   # il cluster 0 vive in 2 shot, il cluster 1 in 3
    ids, sospetti = split_by_reliability(labels, scores, shots)
    assert sospetti == set()
    assert list(ids) == [-1, -1, -1, 1, 1, 1]


def test_refine_clusters_separa_un_cluster_fuso():
    """Il gruppo più numeroso tiene l'id, gli altri se ne prendono uno nuovo."""
    from scene_detector.recognition.identify import refine_clusters

    body = np.vstack([_blob(11, 8), _blob(12, 6)])   # un cluster ArcFace, due identità vere
    labels = np.zeros(14, int)
    out, spezzati = refine_clusters(labels, body, {0}, threshold=0.5, min_size=5)
    assert len(set(out)) == 2
    assert len(set(out[:8])) == 1 and len(set(out[8:])) == 1
    assert out[0] == 0                                # il gruppo da 8 tiene l'id originale
    assert spezzati == {0, 1}


def test_refine_clusters_lascia_intatto_cio_che_non_si_separa():
    """Meglio un cluster fuso noto che una frammentazione inventata."""
    from scene_detector.recognition.identify import refine_clusters

    labels = np.zeros(12, int)
    out, spezzati = refine_clusters(labels, _blob(13, 12), {0}, threshold=0.5, min_size=5)
    assert list(out) == list(labels) and spezzati == set()


def test_refine_clusters_ignora_i_cluster_troppo_piccoli():
    from scene_detector.recognition.identify import refine_clusters

    body = np.vstack([_blob(14, 4), _blob(15, 4)])   # 8 membri: sotto 2*min_size
    labels = np.zeros(8, int)
    out, spezzati = refine_clusters(labels, body, {0}, threshold=0.5, min_size=5)
    assert list(out) == list(labels) and spezzati == set()


def test_refine_clusters_non_tocca_i_cluster_fuori_da_targets():
    """Gli umani non passano di qui per costruzione: solo i sospetti vengono rimessi in gioco."""
    from scene_detector.recognition.identify import refine_clusters

    body = np.vstack([_blob(16, 8), _blob(17, 6)])
    labels = np.array([0] * 8 + [1] * 6)
    out, spezzati = refine_clusters(labels, body, set(), threshold=0.5, min_size=5)
    assert list(out) == list(labels) and spezzati == set()


def test_train_adapter_senza_due_identita_non_addestra():
    """Meno di due maestri: non c'è invarianza da imparare, e il chiamante deve accorgersene."""
    from scene_detector.recognition.adapt import train_adapter

    assert train_adapter(_blob(18, 6), np.full(6, -1)) is None
    assert train_adapter(_blob(19, 6), np.zeros(6, int), device="cpu") is None


def test_train_adapter_avvicina_la_stessa_identita():
    """Il segnale: dopo l'adattamento le coppie intra-identità stanno più vicine delle inter."""
    from scene_detector.recognition.adapt import project, train_adapter

    emb = np.vstack([_blob(20, 10, spread=0.35), _blob(21, 10, spread=0.35)])
    ids = np.array([0] * 10 + [1] * 10)
    W = train_adapter(emb, ids, dim=16, steps=60, device="cpu")
    z = project(emb, W)
    intra = (z[:10] @ z[:10].T).mean() + (z[10:] @ z[10:].T).mean()
    assert intra / 2 > (z[:10] @ z[10:].T).mean()


def test_body_crop_resta_dentro_l_inquadratura():
    """Il box di figura eccede quasi sempre il frame: va tagliato, non deve uscire."""
    from PIL import Image

    from scene_detector.recognition.embed import body_crop

    img = Image.new("RGB", (640, 272))
    crop = body_crop(img, (353, 90, 405, 146))
    assert crop.width <= 640 and crop.height <= 272 and crop.width > 0 and crop.height > 0


def test_letterbox_preserva_le_proporzioni():
    """Schiacciare una figura 1:2 in un quadrato ne distrugge la sagoma."""
    from PIL import Image

    from scene_detector.recognition.embed import letterbox

    out = letterbox(Image.new("RGB", (100, 300), (255, 0, 0)), size=224)
    assert out.size == (224, 224)
    assert out.getpixel((112, 112)) == (255, 0, 0)      # il contenuto sta al centro
    assert out.getpixel((5, 112)) != (255, 0, 0)        # i lati sono riempimento


def test_refine_usa_la_propria_soglia_non_quella_di_arcface():
    """Regressione: `_refine` deve usare la soglia che riceve, non 0,5 di ArcFace.

    Il bug spedito il 25 lug: la soglia di ArcFace applicata allo spazio DINOv2 adattato lasciava
    Vader e gli stormtrooper in un cluster solo (purezza 0,43 contro 0,98 alla soglia giusta).
    """
    from scene_detector.recognition.faces import _refine

    # due identita' maestre affidabili (det alto, piu' shot) + un sospetto che ne fonde due
    body = np.vstack([_blob(31, 12), _blob(32, 12), _blob(33, 10), _blob(34, 10)])
    labels = np.array([0] * 12 + [1] * 12 + [2] * 20)
    scores = np.array([0.8] * 24 + [0.55] * 20)
    shots = np.array(list(range(12)) + list(range(12)) + list(range(20)))

    # -1,0 fa passare qualunque coseno: tutto resta fuso, comunque sia l'adattatore. Una soglia
    # solo "bassa" non basta — dopo la proiezione due identità stanno anche a coseno negativo.
    largo, nessuno = _refine(labels, scores, shots, body, threshold=-1.0)
    stretto, spezzati = _refine(labels, scores, shots, body, threshold=0.9)
    assert len(set(largo[labels == 2])) == 1 and not nessuno   # resta fuso
    assert len(set(stretto[labels == 2])) > 1 and spezzati      # si separa


def test_refine_threshold_ha_un_default_diverso_da_faces_threshold():
    """I due parametri vivono in spazi di embedding diversi: condividere il default è il bug."""
    from scene_detector.core.config import Config

    c = Config(video="x")
    assert c.faces_refine_threshold != c.faces_threshold
