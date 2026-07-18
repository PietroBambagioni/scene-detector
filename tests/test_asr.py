from scene_detector.transcription.asr import is_hallucination


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
