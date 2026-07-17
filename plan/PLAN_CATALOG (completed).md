# Implementation Plan — Catalogo Scene (ASR + UI)

## Obiettivo
Da film → **catalogo shot navigabile**: elenco ordinato (shot 1..N, uno per stacco macchina),
per ogni shot i **dialoghi trascritti** e (in futuro) una **descrizione visiva**; una **UI**
con link che salta alla scena nel video, per revisione/correzione manuale.

Il taglio in clip è un mezzo per strutturare, non il fine. **VLM rimandato** (fase successiva).

## Stato di partenza
- Segmentazione shot: **FATTA** (`transnet` / `pyscenedetect` / `ensemble`).
- Manifest JSON: **FATTO** (Inc 1) — backbone con campi `dialogue`/`description` vuoti.

## Architettura (VLM = fase successiva)
```
film ─► shot detection (FATTO) ─► manifest.json (shot + tempi + clip)
     ├─ audio (ffmpeg) ─► Whisper ─► segmenti (timestamp) ─► allinea a shot ─► dialogue
     └─ [DOPO] keyframe ─► VLM locale ─► description
                 ▼
        manifest.json completo ─► UI HTML (video + seek + edit + export JSON)
```

## Moduli nuovi
- `asr.py` — estrai audio (ffmpeg), trascrivi con faster-whisper, ritorna segmenti (start, end, text).
- `align.py` — mappa i segmenti ASR sugli shot per overlap temporale.
- `catalog.py` — orchestrazione: detection → manifest → ASR → (dopo) VLM → UI.
- `ui.py` — genera HTML self-contained dal manifest + path del video.
- CLI: nuovo comando `catalog` (o estensione del comando attuale).
- [DOPO] `caption.py` — VLM keyframe → description.

## Data model (manifest esteso)
Per shot: `index`, `start/end_frame`, `start/end_time`, `clip`, `confidence`,
**`dialogue`** (testo unito dei segmenti che cadono nello shot), `description` (null per ora).

## Steps (con verifica)
1. **[FATTO]** Manifest JSON → file valido, shot con tempi/clip.
2. **Clip di test reale** da `Anna.mp4` (~2 min) → ha audio + stacchi (i color-bar non servono).
3. **`asr.py`**: audio + faster-whisper + timestamp → trascrizione IT sensata sulla clip.
4. **`align.py`**: segmenti → shot per overlap → unit-test su input sintetici + dialoghi coerenti.
5. **Riempi manifest** con `dialogue` + comando CLI `catalog` → manifest con dialoghi per shot.
6. **`ui.py`**: HTML (`<video>` locale, lista shot, click → `currentTime`, textarea editabili,
   export JSON) → nel browser i link saltano, editing + export funzionano.
7. **[DOPO]** VLM description.

## Decisioni prese
- Granularità: **shot-level** (una voce per stacco).
- ASR: **faster-whisper** (CPU int8; modello `medium`/`large-v3` per IT; timestamp a segmento).
- VLM: locale MPS (Qwen2-VL-2B) — **rimandato**.
- UI: HTML self-contained; il video (7.9 GB) **referenziato per path** (`file://`), non incorporato.

## Deps nuove
- `faster-whisper` (in installazione). Modello Whisper scaricato al primo uso (~770 MB `medium`,
  ~1.5 GB `large-v3`).
- UI e manifest: nessuna dipendenza (HTML/JSON puri).

## Scaling / gotcha
- Film 3.5h: ASR faster-whisper CPU = minuti–decine di minuti (dipende dal modello);
  `mlx-whisper` (Metal) è l'alternativa più veloce su Apple Silicon se serve.
- UI: niente embedding del film da 7.9 GB → `<video src="file://…">` locale; le clip già tagliate
  restano come fallback per-shot.
- **Testare sempre prima sulla clip da 2 min**, mai sul film intero.

## Ordine
2 → 3 → 4 → 5 → 6. VLM (7) in una fase separata.

## Stato
- **[FATTO]** 1 Manifest · 2 clip test · 3 ASR (faster-whisper, VAD, modello a runtime) ·
  4 align (+unit-test) · 5 manifest con dialoghi + CLI `--asr/--asr-model/--asr-lang` ·
  6 UI HTML (`index.html`: player + lista + editing + export JSON).
- Verificato end-to-end su clip reale Anna (2 min): 5 shot, 90 segmenti IT, 4 con dialogo, UI navigabile.
- Suite test: **15/15**.
- **Rimane**: 7 VLM description (rimandato).
