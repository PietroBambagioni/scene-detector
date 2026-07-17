import numpy as np
import pytest

from scene_detector.detectors._neural import FrameWindower


def _batch_windows(frames):
    """Ricostruisce le finestre come il windowing batch dei predictor (wrapper.py)."""
    n = len(frames)
    pad_end = 25 + 50 - (n % 50 if n % 50 != 0 else 50)
    padded = np.concatenate(
        [np.repeat(frames[:1], 25, axis=0), frames, np.repeat(frames[-1:], pad_end, axis=0)],
        axis=0,
    )
    n_windows = (len(padded) - 100) // 50 + 1
    return [padded[w * 50:w * 50 + 100] for w in range(n_windows)]


@pytest.mark.parametrize("n", [1, 20, 49, 50, 51, 100, 137, 250])
def test_streaming_windows_match_batch(n):
    frames = np.arange(n * 2 * 2 * 3, dtype=np.uint8).reshape(n, 2, 2, 3)
    expected = _batch_windows(frames)

    windower = FrameWindower(list(frames))
    got = list(windower)

    assert windower.n == n
    assert len(got) == len(expected)
    for g, e in zip(got, expected):
        assert g.shape == (100, 2, 2, 3)
        assert np.array_equal(g, e)


def test_streaming_empty():
    windower = FrameWindower([])
    assert list(windower) == []
    assert windower.n == 0
