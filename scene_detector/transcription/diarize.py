"""Diarizzazione: chi parla, e quando. Poi gli speaker sugli shot.

Backend: `speech` ([speech-swift](https://github.com/soniqo/speech-swift), Apache-2.0), binario
esterno da Homebrew — **non una dipendenza Python**, non tocca il venv e non vuole token
HuggingFace. Stesso schema con cui il progetto tratta ffmpeg: un eseguibile che si invoca.

**Engine `pyannote` e non `sortformer`, ed è misurato** (`plan/VERBALE.md` §7.1): sullo
stesso audio di *Rogue One* sortformer si ferma a **4 parlanti esatti** dove pyannote e community1
ne trovano 6 — è il tetto architetturale che la documentazione di terze parti riportava e che
nessuno aveva verificato. Costa 11 s ogni 600 s di audio contro i 5,4 s di sortformer, cioè ~2,5
minuti su un film di 2 h: irrilevante accanto ai 45 min di ASR+VLM. E il «pyannote ha i modelli
gated», che l'aveva fatto scartare, vale per la libreria Python, non per `speech`.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

log = logging.getLogger("scene_detector")

ENGINE = "pyannote"


def _wav(video_path, dest, sample_rate=16000):
    """Traccia audio mono a `sample_rate` in `dest`. `speech` vuole un file WAV, non uno stream."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", str(sample_rate),
         "-loglevel", "error", str(dest)],
        check=True,
    )


def parse_output(raw):
    """Lo stdout di `speech diarize --json` -> (segmenti, n_speaker dichiarati).

    ⚠️ `speech` scrive i suoi log di avanzamento su **stdout**, davanti al JSON: senza tagliare
    alla prima graffa il parse muore sulla prima riga. I segmenti hanno `speaker` (intero),
    `start`, `end`, `duration`.
    """
    i = raw.find("{")
    if i < 0:
        raise RuntimeError(f"`speech diarize` non ha prodotto JSON: {raw[:200]!r}")
    data = json.loads(raw[i:])
    return data["segments"], data.get("num_speakers")


def diarize(video_path, engine=ENGINE):
    """Chi parla e quando. -> (segmenti [{speaker, start, end, duration}], n_speaker).

    Estrae l'audio in un WAV temporaneo e lo passa a `speech`. Il temporaneo vive quanto la
    chiamata: su un film di 2 h sono ~250 MB di PCM che non vale la pena tenere.
    """
    if shutil.which("speech") is None:
        raise RuntimeError("`--diarize` richiede il binario `speech`: brew install speech")

    with tempfile.TemporaryDirectory(prefix="diarize_") as tmp:
        wav = Path(tmp) / "audio.wav"
        _wav(video_path, wav)
        out = subprocess.run(["speech", "diarize", "--engine", engine, "--json", str(wav)],
                             capture_output=True, text=True, check=True).stdout
    segments, n_speakers = parse_output(out)
    return segments, n_speakers


def assign_speakers(shots, segments):
    """Assegna a ogni shot i parlanti che vi si sentono. `shots` mutata in-place (campo `speakers`).

    **Per sovrapposizione, non per punto medio** — e qui sta la differenza con
    `align.assign_dialogue`, che invece assegna ogni segmento a *uno* shot. Un turno di parola
    attraversa gli stacchi (è normale: campo/controcampo), quindi finisce in **tutti** gli shot che
    tocca. È anche il segnale che `plan/VERBALE.md` §5.9 ha misurato: un parlante che continua
    attraverso un taglio dice «stessa scena».

    Ordinati per secondi di parlato dentro lo shot, decrescente: il primo è chi parla di più.

    Shot contigui e ordinati + segmenti ordinati per inizio → puntatore che non torna indietro,
    come in `assign_dialogue`: O(shot + sovrapposizioni) invece di O(shot × segmenti), che su
    3200 shot e 5000 turni sarebbero 16 milioni di confronti per niente.
    """
    per_shot = [defaultdict(float) for _ in shots]
    first = 0
    for seg in sorted(segments, key=lambda s: s["start"]):
        while first < len(shots) - 1 and shots[first]["end_time"] <= seg["start"]:
            first += 1
        i = first
        while i < len(shots) and shots[i]["start_time"] < seg["end"]:
            overlap = min(seg["end"], shots[i]["end_time"]) - max(seg["start"], shots[i]["start_time"])
            if overlap > 0:
                per_shot[i][int(seg["speaker"])] += overlap
            i += 1
    for shot, talk in zip(shots, per_shot):
        shot["speakers"] = [s for s, _ in sorted(talk.items(), key=lambda kv: (-kv[1], kv[0]))]
    return shots
