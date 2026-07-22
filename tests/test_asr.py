import numpy as np

from scene_detector.transcription.asr import (MAX_WINDOW_S, SAMPLE_RATE, is_hallucination,
                                              speech_head, vad_windows)


def test_blacklist_phrase():
    assert is_hallucination("Grazie a tutti")
    assert is_hallucination("Grazie a tutti.")   # con punteggiatura
    assert is_hallucination("grazie")


def test_blacklist_phrase_looped():
    assert is_hallucination("Grazie a tutti Grazie a tutti")
    assert is_hallucination("Grazie a tutti " * 40)


def test_subtitle_credits():
    assert is_hallucination("Sottotitoli e revisione a cura di QTSS")


def test_degenerate_loop_not_in_blacklist():
    assert is_hallucination("no no no no")
    assert is_hallucination("ecco ecco ecco")


def test_empty_or_whitespace():
    assert is_hallucination("")
    assert is_hallucination("   ...  ")


def test_real_dialogue_kept():
    assert not is_hallucination("Buongiorno, come stai oggi?")
    assert not is_hallucination("Non voglio andarmene da qui")
    assert not is_hallucination("Anna, aspetta un momento")


def test_short_legit_utterance_kept():
    # una battuta breve non ripetuta non deve essere scartata
    assert not is_hallucination("Andiamo")
    assert not is_hallucination("Sì, certo")


# ------------------------------------------------- finestre di decodifica VAD ---

def _ts(*pairs):
    """(start_s, end_s) -> il formato campioni di get_speech_timestamps."""
    return [{"start": int(a * SAMPLE_RATE), "end": int(b * SAMPLE_RATE)} for a, b in pairs]


def test_vad_windows_raggruppa_sotto_il_massimo():
    # tre segmenti vicini entro 30 s: una sola finestra, dal primo start all'ultimo end
    assert vad_windows(_ts((0, 5), (6, 10), (12, 20))) == [(0.0, 20.0)]


def test_vad_windows_apre_una_nuova_oltre_il_massimo():
    # il terzo segmento porterebbe la finestra a 45 s > 30: se ne apre una nuova
    assert vad_windows(_ts((0, 10), (11, 25), (40, 45))) == [(0.0, 25.0), (40.0, 45.0)]


def test_vad_windows_rispetta_il_limite():
    # 20 segmenti di parlato da 3 s ogni 4 s = 80 s di audio -> più finestre, tutte <= 30 s
    windows = vad_windows(_ts(*[(i * 4, i * 4 + 3) for i in range(20)]))
    assert len(windows) > 1
    assert all(b - a <= MAX_WINDOW_S for a, b in windows)
    assert windows[0][0] == 0.0 and windows[-1][1] == 79.0


def test_vad_windows_non_spezza_il_parlato_ininterrotto():
    # un solo segmento da 80 s senza pause: resta intero, si taglia solo nei silenzi
    assert vad_windows(_ts((0, 80))) == [(0.0, 80.0)]


def test_vad_windows_chiude_la_finestra_prima_di_un_segmento_lungo():
    # la finestra corta non viene persa né estesa dal segmento lungo che segue
    assert vad_windows(_ts((0, 5), (6, 76))) == [(0.0, 5.0), (6.0, 76.0)]


def test_vad_windows_vuoto():
    assert vad_windows([]) == []


# --------------------------------------------- rilevamento lingua sul parlato ---

def test_speech_head_salta_il_silenzio_iniziale():
    # audio: 60 s di silenzio (cartello d'apertura) poi 60 s di parlato. Il rilevamento lingua
    # deve vedere la voce, non il silenzio: su Anna questo bug dava `en` su un film italiano.
    audio = np.concatenate([np.zeros(60 * SAMPLE_RATE), np.ones(60 * SAMPLE_RATE)])
    head = speech_head(audio, [(60.0, 120.0)], seconds=30.0)
    assert len(head) == 30 * SAMPLE_RATE
    assert head.min() == 1.0            # solo parlato, nessun campione di silenzio


def test_speech_head_concatena_piu_finestre():
    # parlato spezzettato: le finestre vanno cucite finché non si arriva a `seconds`
    audio = np.arange(120 * SAMPLE_RATE, dtype=np.float32)
    head = speech_head(audio, [(0.0, 10.0), (30.0, 40.0), (60.0, 80.0)], seconds=30.0)
    assert len(head) == 30 * SAMPLE_RATE


def test_speech_head_senza_finestre_usa_l_audio():
    # nessun parlato rilevato: meglio l'audio grezzo che un array vuoto
    audio = np.ones(10 * SAMPLE_RATE)
    assert len(speech_head(audio, [], seconds=30.0)) == 10 * SAMPLE_RATE


def test_speech_head_parlato_piu_corto_del_richiesto():
    audio = np.ones(120 * SAMPLE_RATE)
    assert len(speech_head(audio, [(0.0, 5.0)], seconds=30.0)) == 5 * SAMPLE_RATE
