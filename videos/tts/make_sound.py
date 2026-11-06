"""Copyright-free sound for the videos, synthesised here: a soft chord pad and three effects."""

from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 44100
OUT = Path(__file__).resolve().parent.parent / "public" / "sound"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7)


def note(freq: float, seconds: float, harmonics=(1.0, 0.35, 0.12)) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    wave = sum(a * np.sin(2 * np.pi * freq * (i + 1) * t) for i, a in enumerate(harmonics))
    # A slow chorus wobble so the pad breathes instead of buzzing.
    return wave * (1 + 0.04 * np.sin(2 * np.pi * 0.3 * t))


def envelope(n: int, attack: float, release: float) -> np.ndarray:
    a, r = int(attack * RATE), int(release * RATE)
    env = np.ones(n)
    env[:a] = np.linspace(0, 1, a) ** 2
    env[-r:] *= np.linspace(1, 0, r) ** 2
    return env


def midi(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def pad(total: float) -> np.ndarray:
    """Cmaj7, Am7, Fmaj7, G6 (sus), four seconds each, overlapping, with a soft high bell."""
    chords = [[48, 55, 64, 71], [45, 52, 60, 67], [41, 48, 57, 64], [43, 50, 59, 64]]
    step, hold = 4.0, 5.5
    out = np.zeros(int((total + hold) * RATE))
    t0, k = 0.0, 0
    while t0 < total:
        for m in chords[k % 4]:
            seg = note(midi(m), hold) * envelope(int(hold * RATE), 1.6, 2.4) * 0.11
            i = int(t0 * RATE)
            out[i : i + len(seg)] += seg
        bell = midi(chords[k % 4][-1] + 12)
        seg = note(bell, 2.5, (1.0, 0.2)) * envelope(int(2.5 * RATE), 0.01, 2.3) * 0.035
        i = int((t0 + 1.0) * RATE)
        out[i : i + len(seg)] += seg
        t0 += step
        k += 1
    out = out[: int(total * RATE)]
    # Gentle low-pass: a moving average softens the upper harmonics.
    out = np.convolve(out, np.ones(9) / 9, mode="same")
    return out / (np.abs(out).max() + 1e-9) * 0.55


def pin() -> np.ndarray:
    """A note landing: a short muted tap with a little body."""
    n = int(0.18 * RATE)
    t = np.arange(n) / RATE
    body = np.sin(2 * np.pi * 180 * t * (1 - 0.4 * t / 0.18)) * np.exp(-t * 38)
    click = rng.normal(0, 1, n) * np.exp(-t * 160) * 0.35
    s = np.convolve(body + click, np.ones(5) / 5, mode="same")
    return s / np.abs(s).max() * 0.7


def swipe() -> np.ndarray:
    """A soft whoosh for scene changes: noise swept through a rising band."""
    n = int(0.55 * RATE)
    t = np.arange(n) / RATE
    noise = rng.normal(0, 1, n)
    out = np.zeros(n)
    for i, w in enumerate(np.linspace(40, 6, n).astype(int)):
        lo = max(0, i - w)
        out[i] = noise[lo : i + 1].mean()
    env = np.sin(np.pi * t / t[-1]) ** 2
    s = out * env
    return s / np.abs(s).max() * 0.45


def chime() -> np.ndarray:
    """The closing title: two soft bell notes."""
    seg = np.zeros(int(1.8 * RATE))
    for delay, m in ((0.0, 76), (0.18, 83)):
        part = note(midi(m), 1.6, (1.0, 0.25)) * envelope(int(1.6 * RATE), 0.005, 1.5)
        i = int(delay * RATE)
        seg[i : i + len(part)] += part[: len(seg) - i]
    return seg / np.abs(seg).max() * 0.5


if __name__ == "__main__":
    sf.write(OUT / "pad.wav", pad(250.0), RATE)
    sf.write(OUT / "pin.wav", pin(), RATE)
    sf.write(OUT / "swipe.wav", swipe(), RATE)
    sf.write(OUT / "chime.wav", chime(), RATE)
    print("written:", sorted(p.name for p in OUT.iterdir()))
