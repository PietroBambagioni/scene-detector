import json

from scene_detector.catalog.thumbs import extract_thumbs
from scene_detector.catalog.ui import build_html


def _manifest(n=6, scenes=None):
    m = {
        "video": "Film.mp4", "fps": 25.0, "n_frames": n * 10, "duration": n * 0.4,
        "detector": "transnet", "n_shots": n, "cast": [],
        "shots": [{"index": i, "start_frame": i * 10, "end_frame": i * 10 + 9,
                   "start_time": i * 0.4, "end_time": (i + 1) * 0.4,
                   "clip": f"clip/scene-{i+1:03d}.mp4", "confidence": 1.0,
                   "description": None, "dialogue": None, "characters": []}
                  for i in range(n)],
    }
    if scenes is not None:
        m["n_scenes"] = len(scenes)
        m["scenes"] = scenes
        for s in m["shots"]:
            s["thumb"] = f"thumbs/{s['start_frame']:06d}.jpg"
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
    assert data["shots"][3]["thumb"] == "thumbs/000030.jpg"    # start_frame, non indice


def test_html_ha_i_pezzi_del_terzo_livello():
    """I marcatori che la UI a tre livelli usa: bande, intestazioni, unisci/dividi."""
    html = build_html(_manifest())
    for token in ('id="bands"', ".scene.open .shots", "mergeWithPrev", "splitAt", "checkScenes",
                  "playScene", "sceneOf"):
        assert token in html, token


def test_html_ha_i_comandi_di_riproduzione():
    """Un `id` che non esiste rende `$(...)` null e il gestore muore in silenzio: qui si vede."""
    html = build_html(_manifest())
    for token in ('id="back5"', 'id="fwd5"', 'id="speed"', 'id="stopend"',
                  "$('back5').onclick", "$('fwd5').onclick", "$('stopend').onclick",
                  "$('speed').onchange", "preservesPitch", "defaultPlaybackRate",
                  'aria-pressed', 'value="0.25"', 'value="2"'):
        assert token in html, token
    # il default resta la riproduzione continua: e' il toggle ad armare `stopAt`
    assert "let stopShot = false;" in html


def test_html_ha_i_comandi_delle_scene():
    """Nomi, confini spostabili, eliminazione e dialoghi a comparsa: i pezzi devono uscire."""
    scenes = [{"index": 0, "first_shot": 0, "last_shot": 2, "start_frame": 0, "end_frame": 29,
               "start_time": 0.0, "end_time": 1.2},
              {"index": 1, "first_shot": 3, "last_shot": 5, "start_frame": 30, "end_frame": 59,
               "start_time": 1.2, "end_time": 2.4}]
    html = build_html(_manifest(scenes=scenes))
    for token in ("nomeScena", "function rinomina", "spostaInizio", "spostaFine", "eliminaScena",
                  "forzaDlg", "input.rinomina"):
        assert token in html, token
    # il dialogo si apre nel pannello dello shot, non nelle righe della lista
    assert "let dlgAperto = false, descrAperto = false;" in html
    assert "function apriTendina" in html
    assert 'id="dlgLabel" class="dlgtoggle"' in html and 'id="descrLabel" class="dlgtoggle"' in html
    assert '<textarea id="dialogue" hidden>' in html
    assert '<textarea id="description" hidden' in html


def test_html_salva_nel_browser_e_sa_annullare():
    """Le correzioni vivevano solo nella scheda aperta: chiuderla costava il lavoro fatto."""
    html = build_html(_manifest())
    for token in ("salvaLocale", "ripescaLocale", "localStorage.setItem", "const passato = []",
                  "function ricorda", "function annulla", 'id="annulla"'):
        assert token in html, token
    # l'impronta impedisce di ripescare modifiche che parlano di un catalogo rigenerato
    assert "v.impronta !== impronta" in html
    # scorciatoie: annulla, un frame, play/pausa, taglia, unisci
    for token in ("e.key.toLowerCase() === 'z'", "e.key === 'ArrowLeft'", "e.key === ' '",
                  "e.key === 's' &&", "e.key === 'm' &&"):
        assert token in html, token


def test_html_ha_la_modalita_revisione():
    """La coda usa `confidence` e `transition`, che stanno gia' nel manifest."""
    html = build_html(_manifest())
    for token in ("function daRivedere", "function mostraVista", "function segnaVisto",
                  "function renderCoda", "SOGLIA_DEBOLE", 'id="rivedi"', "sh.rivisto"):
        assert token in html, token
    # entra anche una graduale con confidenza alta: e' li' che i confini sbagliano di piu'
    assert "|| !!shots[i].transition" in html


def test_html_porta_i_font_dentro():
    """`<link>` a Google Fonts fallisce in silenzio da `file://`: i woff2 vanno incorporati."""
    html = build_html(_manifest())
    assert "__FONT__" not in html
    assert html.count("@font-face") >= 3
    assert "data:font/woff2;base64," in html
    assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html


def test_html_esporta_edl_e_srt():
    """I confini stanno gia' al fotogramma: l'EDL e' un cambio di notazione, non una conversione."""
    html = build_html(_manifest())
    for token in ("function edl", "function srt", "FCM: NON-DROP FRAME", "function tc",
                  'id="edl"', 'id="srt"', "sh.end_frame + 1"):
        assert token in html, token


def test_html_ha_scheda_e_filtri():
    html = build_html(_manifest())
    for token in ("function renderScheda", "const FILTRI", "function mostrato", "function passa",
                  'id="scheda"', 'id="filtri"', 'id="ritmo"', "ASL (durata media)"):
        assert token in html, token
    # tre viste, una variabile sola: due booleani si accendono insieme e poi bisogna decidere
    assert "let vista = 'lista';" in html


def test_html_ha_aiuto_ricerche_e_menu_export():
    """L'aiuto viaggia col file: un catalogo si copia e si manda, le istruzioni vanno con lui."""
    html = build_html(_manifest())
    for token in ("function renderAiuto", 'id="aiuto"', "const tasti = [", "<kbd>",
                  'id="filterDescr"', 'id="menuExport"', "<summary>↓ esporta</summary>"):
        assert token in html, token
    # le due ricerche sono indipendenti e si sommano
    assert "$('filterDescr').value.toLowerCase()" in html
    assert "$('filterDescr').value ||" in html
    # ogni scorciatoia del gestore tasti compare anche nella tabella dell'aiuto
    for k in ("spazio", "⌘Z"):
        assert k in html, k


def test_html_sa_fondere_due_personaggi():
    """Il clustering spezza una persona in due gruppi: rimetterli insieme e' lavoro da occhio."""
    html = build_html(_manifest())
    for token in ("function fondiPersonaggi", "let daFondere = null;", "fondi.className = 'fondi'",
                  "dafondere", "bersaglio", "avvisoFusione"):
        assert token in html, token
    # il conteggio si rifa' sui dati: sommarli conta due volte gli shot dove c'erano entrambi
    assert "target.n_shots = shots.filter" in html
    # e l'annulla deve riportare indietro anche il cast, non solo shot e scene
    assert "JSON.stringify({ shots, scenes, cast })" in html


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
    assert [s["thumb"] for s in m["shots"]] == [f"thumbs/{i*10:06d}.jpg" for i in range(3)]
    assert (tmp_path / "thumbs" / "000000.jpg").exists()
    # `fps` viene passato: senza, sugli shot corti si campiona il frame dello shot successivo
    assert calls[0][5] == 25.0

    n2 = extract_thumbs(m, "Film.mp4", tmp_path, progress=False)
    assert n2 == 0                      # file già su disco: nessuna estrazione in più

    # taglio manuale: gli indici scalano, gli start_frame no. Le miniature degli shot rimasti
    # fermi restano valide, e solo quella dello shot nuovo si estrae — col nome per indice
    # avrebbero invece cambiato tutte proprietario, senza rigenerarsi mai.
    m["shots"].insert(1, {**m["shots"][0], "index": 1, "start_frame": 5, "end_frame": 9,
                          "start_time": 0.2, "end_time": 0.4})
    for i, s in enumerate(m["shots"]):
        s["index"] = i
    assert extract_thumbs(m, "Film.mp4", tmp_path, progress=False) == 1
    assert [s["thumb"] for s in m["shots"]] == ["thumbs/000000.jpg", "thumbs/000005.jpg",
                                                "thumbs/000010.jpg", "thumbs/000020.jpg"]


def test_esc_protegge_gli_attributi():
    """`esc` finisce dentro `value="…"`: una virgoletta nel nome chiudeva l'attributo."""
    import shutil
    import subprocess

    import pytest

    if not shutil.which("node"):
        pytest.skip("serve node")
    riga = next(r for r in build_html(_manifest()).splitlines() if r.startswith("const esc ="))
    out = subprocess.run(["node", "-e", riga + ' console.log(esc(\'Mario "il rosso" <&>\'))'],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "Mario &quot;il rosso&quot; &lt;&amp;&gt;"


def _pagine_in_node(scenario):
    """Esegue il blocco salva/ripesca della pagina in node, con due «aperture» simulate.

    `pagina(DATA)` rifà ciò che la pagina fa al caricamento; `scenario` è JS che usa `pagina`,
    `archivio` (il localStorage finto) e scrive su stdout un JSON da controllare.
    """
    import shutil
    import subprocess

    import pytest

    if not shutil.which("node"):
        pytest.skip("serve node")
    script = build_html(_manifest()).split("<script>")[1]
    blocco = script[script.index("const CHIAVE"):script.index("// Tagliare, unire")]
    js = f"""
    const archivio = {{ m: {{}}, getItem(k) {{ return this.m[k] ?? null; }},
                       setItem(k, v) {{ this.m[k] = v; }} }};
    function pagina(DATA) {{
      const localStorage = archivio, $ = () => ({{}});
      const shots = DATA.shots, cast = DATA.cast || [], scenes = DATA.scenes || null;
      const castById = {{}}; cast.forEach(c => castById[c.id] = c);
      {blocco}
      const salva = () => archivio.setItem(CHIAVE, JSON.stringify(differenze()));
      return {{ DATA, shots, cast, castById, scenes, salva, ripescaLocale }};
    }}
    {scenario}
    """
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_il_ripescaggio_non_copre_un_run_nuovo():
    """Dopo un `--vlm` sugli stessi confini, la copia nel browser copriva le descrizioni nuove
    con quelle vecchie (vuote): un export seguito da `--from-manifest` le perdeva davvero."""
    vecchio = _manifest(n=3)
    vecchio["cast"] = [{"id": 0, "name": "Personaggio 1", "n_shots": 2},
                       {"id": 1, "name": "Personaggio 2", "n_shots": 1}]
    vecchio["shots"][0]["characters"] = [0]
    vecchio["shots"][2]["characters"] = [0, 1]
    nuovo = json.loads(json.dumps(vecchio))
    for i, s in enumerate(nuovo["shots"]):
        s["description"] = f"descrizione {i}"                   # il VLM, girato dopo
    r = _pagine_in_node(f"""
      const a = pagina({json.dumps(vecchio)});
      a.shots[0].dialogue = 'corretto a mano';
      a.shots[2].rivisto = true;
      a.castById[1].name = 'Anna';
      // spezza lo shot 1 [10, 19] a 15, come splitShotAt
      a.shots.splice(1, 1, {{...a.shots[1], end_frame: 14, end_time: 0.6}},
                           {{...a.shots[1], start_frame: 15, start_time: 0.6, confidence: null}});
      a.salva();
      const b = pagina({json.dumps(nuovo)});
      console.log(JSON.stringify({{ ok: b.ripescaLocale(), shots: b.shots, cast: b.cast,
                                    n: b.DATA.n_shots }}));
    """)
    assert r["ok"] and r["n"] == 4
    sh = r["shots"]
    assert [(s["start_frame"], s["end_frame"]) for s in sh] == [(0, 9), (10, 14), (15, 19), (20, 29)]
    assert sh[0]["description"] == "descrizione 0"               # il run nuovo resta
    assert sh[0]["dialogue"] == "corretto a mano"                # e la correzione a mano pure
    assert sh[3]["description"] == "descrizione 2" and sh[3]["rivisto"] is True
    assert sh[3]["characters"] == [0, 1]
    assert sh[1]["description"] is None                          # confine nuovo: la pipeline non
    assert sh[2]["confidence"] is None                           # lo conosceva, resta quello salvato
    assert [c["name"] for c in r["cast"]] == ["Personaggio 1", "Anna"]


def test_il_ripescaggio_non_avviene_se_il_detector_ha_spostato_i_confini():
    vecchio, nuovo = _manifest(n=3), _manifest(n=3)
    nuovo["shots"][1]["end_frame"], nuovo["shots"][2]["start_frame"] = 17, 18
    r = _pagine_in_node(f"""
      const a = pagina({json.dumps(vecchio)});
      a.shots[1].dialogue = 'di un altro pezzo di film';
      a.salva();
      const b = pagina({json.dumps(nuovo)});
      console.log(JSON.stringify({{ ok: b.ripescaLocale(), d: b.shots[1].dialogue }}));
    """)
    assert r == {"ok": False, "d": None}


def test_un_salvataggio_del_formato_vecchio_non_va_perso():
    """Le copie intere salvate prima delle differenze tornano com'erano, una volta."""
    m = _manifest(n=3)
    copia = json.loads(json.dumps(m["shots"]))
    copia[1]["dialogue"] = "mai esportato"
    r = _pagine_in_node(f"""
      archivio.setItem('scene-detector:Film.mp4',
                       JSON.stringify({{ impronta: '3/25/0/20', shots: {json.dumps(copia)},
                                         scenes: null, cast: [] }}));
      const b = pagina({json.dumps(m)});
      console.log(JSON.stringify({{ ok: b.ripescaLocale(), d: b.shots[1].dialogue }}));
    """)
    assert r == {"ok": True, "d": "mai esportato"}


def test_scene_rifatte_tengono_i_nomi_dati_a_mano():
    """`--scenes` rifatto sugli stessi shot: vincono le scene nuove, ma i nomi scritti a mano
    tornano dove la scena comincia allo stesso frame."""
    scene = lambda *g: [{"index": i, "first_shot": a, "last_shot": b, "start_frame": a * 10,
                         "end_frame": b * 10 + 9, "start_time": a * 0.4, "end_time": (b + 1) * 0.4}
                        for i, (a, b) in enumerate(g)]
    vecchio, nuovo = _manifest(scenes=scene((0, 2), (3, 5))), _manifest(scenes=scene((0, 3), (4, 5)))
    r = _pagine_in_node(f"""
      const a = pagina({json.dumps(vecchio)});
      a.scenes[0].name = 'Il cortile'; a.scenes[1].name = 'La cena';
      a.salva();
      const b = pagina({json.dumps(nuovo)});
      console.log(JSON.stringify({{ ok: b.ripescaLocale(), scene: b.scenes }}));
    """)
    assert r["ok"]
    assert [(s["first_shot"], s["last_shot"], s.get("name")) for s in r["scene"]] == [
        (0, 3, "Il cortile"), (4, 5, None)]
