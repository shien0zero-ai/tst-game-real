"""Generate deterministic original placeholder game audio; no external samples."""
from pathlib import Path
import math
import random
import struct
import wave

ROOT = Path(__file__).resolve().parents[1]
RATE = 44100


def save(name, duration, sample):
    rng = random.Random(1911)
    values = [math.tanh(sample(i / RATE, rng)) for i in range(int(RATE * duration))]
    peak = max(abs(v) for v in values) or 1.0
    pcm = b"".join(struct.pack("<h", round(v / peak * 24000)) for v in values)
    with wave.open(str(ROOT / "assets" / "audio" / name), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(pcm)


def shot(t, rng):
    noise = rng.uniform(-1, 1)
    transient = noise * math.exp(-t * 65) * 1.6
    body = math.sin(2 * math.pi * (125 * t - 60 * t * t)) * math.exp(-t * 22) * 0.8
    tail = noise * math.exp(-t * 15) * 0.15
    return (transient + body + tail) * min(1.0, t * 5000)


def click(t, rng):
    return (rng.uniform(-1, 1) * 0.65 + math.sin(2 * math.pi * 1700 * t) * 0.35) * math.exp(-t * 100)


def reload(t, rng):
    value = 0.0
    for at, gain in [(0.0, 0.5), (0.48, 0.7), (0.94, 1.0)]:
        local = t - at
        if 0 <= local < 0.16:
            value += gain * (rng.uniform(-1, 1) + math.sin(2 * math.pi * 900 * local) * 0.3) * math.exp(-local * 60)
    return value


if __name__ == "__main__":
    save("pistol_shot.wav", 0.4, shot)
    save("empty.wav", 0.1, click)
    save("reload.wav", 1.2, reload)
