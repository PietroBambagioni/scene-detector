# Implementation Plan — VLM (descrizione visiva per shot)

## Obiettivo
Riempire il campo `description` di ogni shot: breve descrizione (1-2 frasi, in italiano) di
**cosa succede**, generata da fotogrammi campionati dallo shot + il **dialogo** (ASR) come contesto.
Tutto **locale** su Apple Silicon.

## Decisioni (da confermare)
- **Backend / modello** (selezionabile a runtime, come per l'ASR):
  - **SCELTO ✓**: `mlx-vlm` con **Qwen2.5-VL-3B-Instruct 4-bit** (`mlx-community`) — nativo
    Metal, veloce su M-series, leggero in 4-bit.
  - (alt. portabile) HF `transformers` + MPS con Qwen2-VL-2B-Instruct.
  - (alt. leggero) `moondream2` (single-image, qualità base).
- **Frame per shot**: default **3** (inizio/metà/fine) — cattura l'azione meglio di 1 solo.
  Configurabile; più frame = più contesto ma più lento.
- **Risoluzione**: ~384–512px lato lungo (compromesso qualità/velocità/token).
- **Output**: italiano, 1-2 frasi, concreto (chi / dove / azione). Dialogo come contesto nel prompt.

## Moduli nuovi
- `caption.py`:
  - `sample_frames(video, shot, n, size)` → PIL images via ffmpeg ai timestamp dello shot.
  - backend VLM astratto: `describe(frames, dialogue) -> str` (impl MLX-VLM; opz. transformers).
  - `caption_manifest(manifest, video, ...)` → riempie `description`, **incrementale e resumable**.
- CLI: `--vlm`, `--vlm-model`, `--vlm-frames`.

## Scala / produzione (critico)
- 2000-3000 shot × inference = **il pezzo più lungo** (ordine ~1-4h sul film intero).
- **Resumable / idempotente**: salva il manifest dopo ogni shot (o ogni N); a un nuovo run
  **salta gli shot che hanno già `description`**. Un crash/stop non perde lavoro.
- **Barra progressi in %** sugli shot + ETA.
- Leve di velocità: MLX 4-bit · meno frame · saltare micro-shot (< soglia) · risoluzione bassa.
- Sequenziale dopo l'ASR (il VLM carica dopo; ~4-6 GB, meno in 4-bit).

## Step (con verifica)
1. `sample_frames` → estrai N frame reali da uno shot — verify: N immagini ai tempi giusti.
2. Backend VLM (MLX-VLM) load + `describe` su 1 shot — verify: descrizione IT sensata su frame reali (Anna).
3. Prompt (frames + dialogo) — verify: qualità su 3-4 shot diversi.
4. `caption_manifest` incrementale + **resume** — verify: interrompi e riprendi → non ricalcola.
5. CLI `--vlm` + barra % — verify: end-to-end su clip 2 min, `description` riempite, la UI le mostra (già predisposta).
6. Unit-test utility (sampling/skip già-fatti).

## Deps
- MLX: `mlx-vlm` (+ modello `mlx-community` 4-bit scaricato al primo uso).
- (alt.) transformers: `transformers`, `accelerate`, `qwen-vl-utils`, `pillow`.

## Note
- Testare sempre prima sulla clip 2 min (poche shot), mai sul film intero.
- La UI mostra e rende editabile `description`: gli errori del VLM li correggi a mano.
- Il prompt include il dialogo → descrizioni più fedeli a "cosa succede".

## Ordine
1 → 2 → 3 → 4 → 5.
