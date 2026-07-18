from __future__ import annotations

import logging
import re

from ..core.cpu import resolve_workers

log = logging.getLogger("scene_detector")


# ----------------------------------------------------- filtro allucinazioni ---
# Whisper, sul non-parlato italiano degradato (fruscio, ronzio), fabbrica frasi-tipo
# ("Grazie a tutti", crediti di sottotitoli) e loop di ripetizione. Le scartiamo a monte:
# uno shot il cui unico contenuto è una di queste NON è dialogo.

_HALLUCINATION_PHRASES = {
    "grazie", "grazie a tutti", "grazie a voi", "grazie mille",
    "grazie a tutti per l attenzione",
}


def _normalize(text):
    """Minuscolo, punteggiatura → spazio, spazi collassati. -> stringa normalizzata."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _min_period(words):
    """Il più corto prefisso la cui ripetizione ricostruisce l'intera lista (sé stesso se aperiodico)."""
    n = len(words)
    for k in range(1, n // 2 + 1):
        if n % k == 0 and all(words[i] == words[i % k] for i in range(n)):
            return words[:k]
    return words


def is_hallucination(text):
    """True se il segmento è un'allucinazione ASR: frase-tipo, crediti sottotitoli o loop."""
    words = _normalize(text).split()
    if not words:
        return True
    base = _min_period(words)
    joined = " ".join(base)
    reps = len(words) // len(base)
    if joined.startswith("sottotitoli"):          # crediti fabbricati
        return True
    if joined in _HALLUCINATION_PHRASES:           # frase canonica, anche ripetuta N volte
        return True
    if reps >= 3 and len(base) <= 5:               # loop degenerato non in blacklist
        return True
    return False


# ------------------------------------------------------------------- ASR -------

def transcribe(video_path, model="large-v3-turbo", language=None, vad=True,
               device="cpu", compute_type="int8", cpu_threads=0, progress=True):
    """Trascrive i dialoghi con faster-whisper.

    Ritorna (segments, detected_language) con segments = list[{start, end, text}].
    VAD (silero) attivo di default: salta musica/silenzio -> meno allucinazioni + più veloce.
    `condition_on_previous_text=False`: taglia il feedback loop che genera le ripetizioni.
    I segmenti riconosciuti come allucinazione (`is_hallucination`) vengono scartati.
    `model` accetta un nome (tiny/base/small/medium/large-v3/large-v3-turbo) o un path.
    `cpu_threads`: thread CTranslate2 (0 = auto: tutti i core meno 2). La barra avanza sui secondi di audio.
    """
    from faster_whisper import WhisperModel
    from tqdm import tqdm

    threads = resolve_workers(cpu_threads)
    wm = WhisperModel(model, device=device, compute_type=compute_type, cpu_threads=threads)
    segments, info = wm.transcribe(str(video_path), language=language, vad_filter=vad,
                                   condition_on_previous_text=False)

    total = getattr(info, "duration", None)
    bar = tqdm(total=round(total, 1) if total else None, unit="s", unit_scale=True,
               desc=f"[asr] {model} ({threads}t)", disable=not progress)
    out, last, dropped = [], 0.0, 0
    for seg in segments:
        text = seg.text.strip()
        if text and not is_hallucination(text):
            out.append({"start": seg.start, "end": seg.end, "text": text})
        elif text:
            dropped += 1
        if total:
            bar.update(max(0.0, seg.end - last))
            last = seg.end
    if total:
        bar.n = round(total, 1)
        bar.refresh()
    bar.close()
    if dropped:
        log.info("[asr] %d segmenti scartati come allucinazioni", dropped)
    return out, info.language
