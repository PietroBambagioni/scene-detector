from __future__ import annotations

import logging
import subprocess
from io import BytesIO
from pathlib import Path

from ..catalog.manifest import load_manifest, write_manifest

log = logging.getLogger("scene_detector")


# ---------------------------------------------------------------- sampling ---

def _timestamps(start, end, n):
    """n istanti in [start, end), leggermente rientrati per evitare i frame di taglio."""
    dur = max(0.0, end - start)
    if n <= 1:
        return [start + dur / 2]
    inset = min(0.15 * dur, 0.3)
    a, b = start + inset, end - inset
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def _extract_frame(video, t, size):
    """Un frame PIL al tempo t, lato lungo <= size, via ffmpeg (seek in input, veloce)."""
    from PIL import Image

    cmd = [
        "ffmpeg", "-nostdin", "-v", "error",
        "-ss", f"{max(0.0, t):.3f}", "-i", str(video),
        "-frames:v", "1",
        "-vf", f"scale='min({size},iw)':'min({size},ih)':force_original_aspect_ratio=decrease",
        "-f", "image2pipe", "-vcodec", "png", "-",
    ]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return Image.open(BytesIO(out)).convert("RGB")


def sample_frames(video, start_time, end_time, n=3, size=512):
    """Estrae n frame PIL campionati in ordine cronologico dallo shot [start_time, end_time)."""
    return [_extract_frame(video, t, size) for t in _timestamps(start_time, end_time, n)]


# ------------------------------------------------------------------ prompt ---

def build_prompt(n_frames, dialogue=None, characters=None):
    """Prompt IT: descrizione concreta di 1-2 frasi; personaggi (face-rec) e dialogo (ASR) come contesto."""
    imgs = "un fotogramma campionato" if n_frames == 1 else \
        f"{n_frames} fotogrammi campionati in ordine cronologico"
    parts = [
        f"Queste immagini sono {imgs} da una singola inquadratura di un film.",
        "Descrivi in italiano, in 1-2 frasi concise, cosa succede: chi è presente, dove si "
        "svolge la scena e l'azione principale. Sii concreto e non inventare dettagli non visibili.",
    ]
    if characters:
        parts.append(
            "Personaggi riconosciuti in questa inquadratura: " + ", ".join(characters)
            + ". Usa questi nomi nella descrizione se corrispondono a chi è visibile."
        )
    if dialogue:
        # il dialogo ha già un campo suo nel manifest: senza questo vincolo il modello lo
        # parafrasa invece di descrivere l'immagine (misurato: 1,4% degli shot sull'8B-4bit)
        parts.append(
            f'Dialogo pronunciato in questa inquadratura (solo contesto): "{dialogue}". '
            "Non ripeterlo né parafrasarlo: descrivi ciò che si vede."
        )
    return "\n".join(parts)


# ------------------------------------------------------------- MLX backend ---

class MlxVlmCaptioner:
    """Backend VLM su MLX (Qwen3-VL-8B 4-bit). Carica il modello una volta, descrive per shot."""

    def __init__(self, model_path="mlx-community/Qwen3-VL-8B-Instruct-4bit",
                 max_tokens=128, temperature=0.0):
        # greedy: per un catalogo la riproducibilità vale più della varietà — la stessa
        # inquadratura deve dare la stessa descrizione a ogni run (e i confronti fra modelli
        # sono stati fatti tutti a temperature=0).
        from mlx_vlm import load
        from mlx_vlm.utils import load_config

        # transformers ristampa "Kwargs passed to processor.__call__…" a **ogni** shot (migliaia
        # per film): spezza la progress bar tqdm e sommerge il log. È un avviso di terze parti
        # sul modo in cui mlx-vlm chiama il processor, non un problema nostro. Solo error+.
        from transformers.utils import logging as hf_logging
        hf_logging.set_verbosity_error()

        self.model, self.processor = load(model_path)
        self.config = load_config(model_path)
        self.max_tokens = max_tokens
        self.temperature = temperature

    def describe(self, frames, dialogue=None, characters=None):
        import os
        import tempfile
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        prompt = build_prompt(len(frames), dialogue, characters)
        formatted = apply_chat_template(self.processor, self.config, prompt, num_images=len(frames))

        # mlx-vlm 0.6.5: generate vuole path di immagini, non PIL -> PNG temporanei
        tmp = tempfile.mkdtemp(prefix="vlm_")
        paths = []
        try:
            for i, im in enumerate(frames):
                p = os.path.join(tmp, f"{i}.png")
                im.save(p)
                paths.append(p)
            result = generate(
                self.model, self.processor, formatted, paths,
                max_tokens=self.max_tokens, temperature=self.temperature, verbose=False,
            )
        finally:
            for p in paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
            try:
                os.rmdir(tmp)
            except OSError:
                pass

        text = result if isinstance(result, str) else getattr(result, "text", str(result))
        return text.strip()


# ------------------------------------------------------------- manifest -----

def caption_manifest(manifest, video, captioner, n_frames=3, size=512,
                     manifest_path=None, progress=True):
    """Riempie `description` per ogni shot. Incrementale e resumable.

    Salta gli shot che hanno già una descrizione (resume da un run precedente su disco, se
    `manifest_path` esiste). Salva il manifest a ogni shot descritto: un crash non perde lavoro.
    """
    from tqdm import tqdm

    shots = manifest["shots"]
    cast_names = {c["id"]: c["name"] for c in manifest.get("cast", [])}  # id cluster → nome (face-rec)

    # resume cross-run: riporta le descrizioni già salvate su disco
    if manifest_path and Path(manifest_path).exists():
        prior = {s["index"]: s.get("description") for s in load_manifest(manifest_path)["shots"]}
        for s in shots:
            if not s.get("description") and prior.get(s["index"]):
                s["description"] = prior[s["index"]]

    done = sum(1 for s in shots if s.get("description"))
    bar = tqdm(total=len(shots), initial=done, desc="[vlm]", unit="shot", disable=not progress)
    failed = 0
    for shot in shots:
        if shot.get("description"):
            continue
        try:
            frames = sample_frames(video, shot["start_time"], shot["end_time"], n_frames, size)
            chars = [cast_names[c] for c in shot.get("characters", []) if c in cast_names]
            shot["description"] = captioner.describe(frames, shot.get("dialogue"), chars or None)
        except Exception as e:  # uno shot "velenoso" non deve fermare il batch (resume-friendly)
            failed += 1
            log.warning("shot %s: descrizione fallita (%s) — proseguo", shot.get("index"), e)
            bar.update(1)
            continue
        if manifest_path:
            write_manifest(manifest, manifest_path)
        bar.update(1)

    bar.close()
    if failed:
        log.warning("VLM: %d shot su %d falliti (descrizione mancante)", failed, len(shots))
    return manifest
