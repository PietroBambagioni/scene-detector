import pytest

from scene_detector.transcription.diarize import assign_speakers, parse_output


def _shots(bounds):
    """[(start, end), …] secondi -> shot del manifest."""
    return [{"index": i, "start_time": a, "end_time": b} for i, (a, b) in enumerate(bounds)]


def test_parse_output_salta_i_log_davanti_al_json():
    """`speech` scrive l'avanzamento su stdout, davanti al JSON: senza tagliare, il parse muore."""
    raw = ('Loading audio: /tmp/a.wav\n  Loaded 9600000 samples (600.00s)\n'
           '  [80%] Downloading model...\nRunning diarization (pyannote)...\n'
           '{\n "segments" : [ {"speaker" : 0, "start" : 2, "end" : 2.5, "duration" : 0.5} ],\n'
           ' "num_speakers" : 3\n}\n')
    segments, n = parse_output(raw)
    assert n == 3
    assert segments == [{"speaker": 0, "start": 2, "end": 2.5, "duration": 0.5}]


def test_parse_output_senza_json_e_un_errore():
    with pytest.raises(RuntimeError, match="non ha prodotto JSON"):
        parse_output("speech: command failed\n")


def test_un_turno_di_parola_entra_in_tutti_gli_shot_che_tocca():
    """È la differenza con `assign_dialogue`: un parlante attraversa gli stacchi (campo/controcampo)
    e non va assegnato a un solo shot. È anche il segnale «stessa scena» di VERBALE §5.9."""
    shots = _shots([(0, 10), (10, 20), (20, 30)])
    assign_speakers(shots, [{"speaker": 1, "start": 8.0, "end": 22.0, "duration": 14.0}])
    assert [s["speakers"] for s in shots] == [[1], [1], [1]]


def test_speakers_ordinati_per_secondi_di_parlato():
    shots = _shots([(0, 10)])
    assign_speakers(shots, [
        {"speaker": 0, "start": 0.0, "end": 1.0, "duration": 1.0},
        {"speaker": 7, "start": 1.0, "end": 6.0, "duration": 5.0},   # parla di più
        {"speaker": 3, "start": 6.0, "end": 8.0, "duration": 2.0},
    ])
    assert shots[0]["speakers"] == [7, 3, 0]


def test_shot_muto_ha_lista_vuota():
    shots = _shots([(0, 10), (10, 20)])
    assign_speakers(shots, [{"speaker": 0, "start": 11.0, "end": 12.0, "duration": 1.0}])
    assert shots[0]["speakers"] == []
    assert shots[1]["speakers"] == [0]


def test_la_sovrapposizione_nulla_non_conta():
    """Un turno che finisce esattamente dove lo shot comincia non lo tocca: `end_time` è esclusivo
    (`(end_frame + 1) / fps`), quindi la sovrapposizione è zero, non un frame."""
    shots = _shots([(0, 10), (10, 20)])
    assign_speakers(shots, [{"speaker": 0, "start": 5.0, "end": 10.0, "duration": 5.0}])
    assert [s["speakers"] for s in shots] == [[0], []]


def test_segmenti_disordinati_non_ingannano_il_puntatore():
    """Il puntatore non torna indietro, quindi i segmenti vanno ordinati: se l'ordinamento
    sparisce, questo test resta l'unico a dirlo."""
    shots = _shots([(0, 10), (10, 20), (20, 30)])
    segments = [{"speaker": 2, "start": 25.0, "end": 28.0, "duration": 3.0},
                {"speaker": 1, "start": 1.0, "end": 4.0, "duration": 3.0},
                {"speaker": 0, "start": 12.0, "end": 15.0, "duration": 3.0}]
    assign_speakers(shots, segments)
    assert [s["speakers"] for s in shots] == [[1], [0], [2]]
