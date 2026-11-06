"""Narration with Kokoro (Apache 2.0, runs offline on the CPU).

Usage: python tts/kokoro_say.py <voice> <out.wav> "text"   (one clip)
       python tts/kokoro_say.py <voice> <script.json> <out_dir>   (every line of a script)
"""

import json
import sys
from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro

MODELS = Path(__file__).resolve().parent.parent / ".tts" / "models"
kokoro = Kokoro(str(MODELS / "kokoro-v1.0.int8.onnx"), str(MODELS / "voices-v1.0.bin"))


def say(voice: str, text: str, out: Path, speed: float = 0.95) -> float:
    lang = "en-gb" if voice.startswith("b") else "en-us"
    samples, rate = kokoro.create(text, voice=voice, speed=speed, lang=lang)
    sf.write(out, samples, rate)
    return len(samples) / rate


if __name__ == "__main__":
    voice, target = sys.argv[1], Path(sys.argv[2])
    if target.suffix == ".json":
        out_dir = Path(sys.argv[3])
        out_dir.mkdir(parents=True, exist_ok=True)
        timings = {}
        for scene in json.loads(target.read_text(encoding="utf-8")):
            speed = scene.get("speed", 0.95)
            timings[scene["id"]] = round(say(voice, scene["say"], out_dir / f"{scene['id']}.wav", speed), 3)
            print(scene["id"], timings[scene["id"]], "s")
        (out_dir / "timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
    else:
        print(round(say(voice, sys.argv[3], target), 2), "s ->", target)
