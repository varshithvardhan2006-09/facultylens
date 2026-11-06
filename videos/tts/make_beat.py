"""The promo's music, synthesised here (no samples): 100 BPM, C G Am F, intro, riser, drop, outro.

Also writes the promo's interaction sounds: a click, a key tap and the snap impact.
Bars are numbered from 1; the drop lands on bar 6 (12.0 s), where the pile snaps into the wall.
"""

from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 44100
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT
BARS = 32  # 76.8 s, the promo's length
DROP_BAR, OUTRO_BAR = 6, 31
OUT = Path(__file__).resolve().parent.parent / "public" / "sound"
rng = np.random.default_rng(11)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def t_of(n):
    return np.arange(n) / RATE


def add(buf, sig, at):
    i = int(at * RATE)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[: j - i]


def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same")


def kick():
    n = int(0.35 * RATE)
    t = t_of(n)
    freq = 110 * np.exp(-t * 18) + 42
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    return np.sin(phase) * np.exp(-t * 9) * 0.9


def clap():
    n = int(0.22 * RATE)
    t = t_of(n)
    noise = rng.normal(0, 1, n)
    body = noise - lowpass(noise, 6)  # keep the bright part
    env = np.exp(-t * 26) + 0.4 * np.exp(-((t - 0.012) ** 2) / 0.00002)
    return body * env * 0.28


def hat(open_=False):
    n = int((0.12 if open_ else 0.05) * RATE)
    t = t_of(n)
    noise = rng.normal(0, 1, n)
    hi = noise - lowpass(noise, 3)
    return hi * np.exp(-t * (30 if open_ else 90)) * 0.16


def pluck(m, length=0.32):
    n = int(length * RATE)
    t = t_of(n)
    f = midi(m)
    sig = np.sin(2 * np.pi * f * t) + 0.45 * np.sin(4 * np.pi * f * t) + 0.18 * np.sin(6 * np.pi * f * t)
    return sig * np.exp(-t * 9) * 0.16


def bass(m, length):
    n = int(length * RATE)
    t = t_of(n)
    f = midi(m)
    sig = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)
    env = np.minimum(1, t / 0.01) * np.exp(-t * 2.2)
    return sig * env * 0.32


def pad_chord(notes, length):
    n = int(length * RATE)
    t = t_of(n)
    sig = sum(np.sin(2 * np.pi * midi(m) * t) + 0.25 * np.sin(4 * np.pi * midi(m) * t) for m in notes)
    env = np.minimum(1, t / 0.6) * np.minimum(1, (length - t) / 0.5)
    return lowpass(sig * env, 7) * 0.05


CHORDS = [  # (root for bass, pad voicing, arpeggio notes)
    (36, [60, 64, 67], [72, 76, 79, 76]),  # C
    (43, [59, 62, 67], [71, 74, 79, 74]),  # G
    (45, [60, 64, 69], [72, 76, 81, 76]),  # Am
    (41, [60, 65, 69], [72, 77, 81, 77]),  # F
]


def music():
    total = BARS * BAR + 3.0
    buf = np.zeros(int(total * RATE))
    for b in range(1, BARS + 1):
        start = (b - 1) * BAR
        root, voicing, arp = CHORDS[(b - 1) % 4]
        groove = DROP_BAR <= b < OUTRO_BAR
        add(buf, pad_chord(voicing, BAR + 0.4), start)
        for beat in range(4):
            at = start + beat * BEAT
            if b < OUTRO_BAR:
                add(buf, hat(), at + BEAT / 2)
                if b >= 3:
                    add(buf, hat(), at)
            if groove:
                if beat in (0, 2):
                    add(buf, kick(), at)
                if beat in (1, 3):
                    add(buf, clap(), at)
                add(buf, bass(root, BEAT * 0.9), at)
            elif 3 <= b < DROP_BAR and beat == 0:
                add(buf, kick() * 0.6, at)
            # The arpeggio comes in at bar 3 and plays eighth notes from the drop.
            if b >= 3 and b < OUTRO_BAR:
                add(buf, pluck(arp[beat]), at)
                if groove:
                    add(buf, pluck(arp[(beat + 2) % 4] + 12, 0.2) * 0.6, at + BEAT / 2)
    # Riser into the drop: noise swelling through bar 5.
    rise_len = BAR
    t = t_of(int(rise_len * RATE))
    noise = rng.normal(0, 1, len(t))
    riser = noise - lowpass(noise, 4)
    add(buf, riser * (t / rise_len) ** 2.5 * 0.22, (DROP_BAR - 2) * BAR)
    # Outro: last chord rings, two bell notes.
    for k, m in enumerate((84, 91)):
        add(buf, pluck(m, 2.2) * 1.4, (OUTRO_BAR - 1) * BAR + k * 0.2)
    buf = np.tanh(buf * 1.4) / np.tanh(1.4)  # gentle glue, no hard clipping
    fade = int(2.5 * RATE)
    buf[-fade:] *= np.linspace(1, 0, fade)
    return buf / np.abs(buf).max() * 0.85


def click():
    n = int(0.06 * RATE)
    t = t_of(n)
    s = np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 120) + rng.normal(0, 1, n) * np.exp(-t * 300) * 0.4
    return s / np.abs(s).max() * 0.6


def key():
    n = int(0.04 * RATE)
    t = t_of(n)
    s = rng.normal(0, 1, n) * np.exp(-t * 180)
    s = lowpass(s, 3)
    return s / np.abs(s).max() * 0.35


def snap():
    n = int(0.9 * RATE)
    t = t_of(n)
    boom = np.sin(2 * np.pi * (60 + 80 * np.exp(-t * 25)) * t) * np.exp(-t * 5)
    crack = rng.normal(0, 1, n) * np.exp(-t * 40) * 0.5
    s = lowpass(boom + crack, 4)
    return s / np.abs(s).max() * 0.8


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    sf.write(OUT / "beat.wav", music(), RATE)
    sf.write(OUT / "click.wav", click(), RATE)
    sf.write(OUT / "key.wav", key(), RATE)
    sf.write(OUT / "snap.wav", snap(), RATE)
    print("beat:", BARS * BAR, "s at", BPM, "BPM; drop at", (DROP_BAR - 1) * BAR, "s")
