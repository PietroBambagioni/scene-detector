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


# --------------------------------------------------------- finestre di decodifica ---
# Trascrivere il film in un'unica chiamata lascia al decoder lo spazio per avvitarsi:
# su Anna produce ancora ripetizioni ("non ti puoi parlare" x3) nonostante
# condition_on_previous_text=False. Decodificare finestre brevi e indipendenti lo impedisce
# per costruzione — ogni finestra riparte da zero — e recupera parlato che altrimenti si perde
# (misurato su 180 s di Anna: 455 -> 488 parole, +18% di tempo).

SAMPLE_RATE = 16000
MAX_WINDOW_S = 30.0


def vad_windows(speech, max_window_s=MAX_WINDOW_S, sample_rate=SAMPLE_RATE):
    """Raggruppa i segmenti di parlato del VAD in finestre di decodifica <= `max_window_s`.

    `speech`: list[{"start": campioni, "end": campioni}] come da `get_speech_timestamps`.
    Una finestra si estende finché resta sotto la durata massima, poi se ne apre una nuova
    **al primo silenzio utile**: `max_window_s` è una soglia, non un taglio netto. Un segmento
    di parlato ininterrotto più lungo resta intero — spezzarlo a metà frase costa parole ai
    bordi (misurato: 488 -> 475 su 180 s), e Whisper lo suddivide comunque nei suoi 30 s.
    -> list[(start_s, end_s)] in secondi, in ordine cronologico.
    """
    windows, cur = [], None
    for s in speech:
        a, b = s["start"] / sample_rate, s["end"] / sample_rate
        if cur is not None and b - cur[0] <= max_window_s:
            cur[1] = b
        else:
            if cur is not None:
                windows.append((cur[0], cur[1]))
            cur = [a, b]
    if cur is not None:
        windows.append((cur[0], cur[1]))
    return windows


def speech_head(audio, windows, seconds=30.0, sample_rate=SAMPLE_RATE):
    """I primi `seconds` di **parlato**, concatenati dalle finestre VAD.

    Rilevare la lingua sull'audio grezzo sbaglia quando il film non apre parlando: i primi 30 s
    di *Anna* sono un cartello muto, Whisper rispondeva `en` su un film italiano e lo trascriveva
    tutto in inglese. Whisper guarda comunque solo i primi 30 s: tanto vale che siano di voce.
    """
    import numpy as np

    need = int(seconds * sample_rate)
    chunks, got = [], 0
    for a, b in windows:
        chunk = audio[int(a * sample_rate):int(b * sample_rate)][:need - got]
        if len(chunk):
            chunks.append(chunk)
            got += len(chunk)
        if got >= need:
            break
    return np.concatenate(chunks) if chunks else audio[:need]


# ------------------------------------------------------------------- ASR -------

def transcribe(video_path, model="large-v3-turbo", language=None, vad=True,
               device="cpu", compute_type="int8", cpu_threads=0, progress=True):
    """Trascrive i dialoghi con faster-whisper.

    Ritorna (segments, detected_language) con segments = list[{start, end, text}].
    Con `vad=True` (default) il parlato viene isolato con il VAD silero e decodificato in
    finestre indipendenti (`vad_windows`): salta musica/silenzio e impedisce i loop di
    ripetizione sulla lunga distanza. Con `vad=False` si trascrive in un'unica passata.
    `condition_on_previous_text=False`: taglia il feedback loop dentro la singola chiamata.
    I segmenti riconosciuti come allucinazione (`is_hallucination`) vengono scartati.
    `model` accetta un nome (tiny/base/small/medium/large-v3/large-v3-turbo) o un path.
    `cpu_threads`: thread CTranslate2 (0 = auto: tutti i core meno 2). La barra avanza sui secondi di audio.
    """
    from faster_whisper import WhisperModel, decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    from tqdm import tqdm

    threads = resolve_workers(cpu_threads)
    wm = WhisperModel(model, device=device, compute_type=compute_type, cpu_threads=threads)

    if vad:
        audio = decode_audio(str(video_path), sampling_rate=SAMPLE_RATE)
        total = len(audio) / SAMPLE_RATE
        # col default (silenzio minimo 2 s) il VAD restituisce un unico segmento lungo quanto
        # il film, e non si spezzerebbe nulla: servono pause più corte per avere dei confini.
        options = VadOptions(min_silence_duration_ms=500)
        windows = vad_windows(get_speech_timestamps(audio, options))
        if language is None:
            language = wm.detect_language(speech_head(audio, windows))[0]
        log.info("[asr] %d finestre di parlato su %.0f s di audio (lingua: %s)",
                 len(windows), total, language)
    else:
        segments, info = wm.transcribe(str(video_path), language=language, vad_filter=False,
                                       condition_on_previous_text=False)
        total, windows, language = getattr(info, "duration", None), None, info.language

    bar = tqdm(total=round(total, 1) if total else None, unit="s", unit_scale=True,
               desc=f"[asr] {model} ({threads}t)", disable=not progress)
    out, last, dropped = [], 0.0, 0

    def collect(segs, offset=0.0):
        """Filtra le allucinazioni e riporta i timestamp all'offset assoluto della finestra."""
        nonlocal last, dropped
        for seg in segs:
            text = seg.text.strip()
            if text and not is_hallucination(text):
                out.append({"start": seg.start + offset, "end": seg.end + offset, "text": text})
            elif text:
                dropped += 1
            if total:
                bar.update(max(0.0, seg.end + offset - last))
                last = seg.end + offset

    if windows is None:
        collect(segments)
    else:
        for a, b in windows:
            segs, _ = wm.transcribe(audio[int(a * SAMPLE_RATE):int(b * SAMPLE_RATE)],
                                    language=language, vad_filter=False,
                                    condition_on_previous_text=False)
            collect(segs, offset=a)

    if total:
        bar.n = round(total, 1)
        bar.refresh()
    bar.close()
    if dropped:
        log.info("[asr] %d segmenti scartati come allucinazioni", dropped)
    return out, language
