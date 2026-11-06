# FacultyLens videos

Two narrated explainer videos, written as code with [Remotion](https://www.remotion.dev) (React)
and rendered to MP4 at 1920×1080, 30 fps.

| Video | Composition | Length | Output |
|---|---|---|---|
| Publishing promo | `Promo` | 76.8 s, cut to a 100 BPM beat, with a tour of each role | `out/facultylens-promo.mp4` |
| How it works (technical) | `Tech` | about 3 min 46 s | `out/facultylens-how-it-works.mp4` |

Everything is made on this computer and is free to publish:

- **Voice:** [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) (Apache 2.0), voice `af_heart`,
  run offline.
- **Music and sound effects:** synthesised by `tts/make_sound.py` (walkthrough pad, effects) and
  `tts/make_beat.py` (the promo's 100 BPM track, clicks, key taps, snap). No samples or third-party audio.
- **Screens:** real screenshots of FacultyLens with its demo data, labelled as demo data on screen.
- **Example scores** in the technical video (sentiment, sarcasm, aspect, redaction) are real outputs
  of the FacultyLens models on those sentences.

## Rebuild

The voice and music files are generated, not committed. From this folder:

```bash
py -3.13 -m venv .tts
```

```bash
.tts\Scripts\python -m pip install kokoro-onnx soundfile
```

Download `kokoro-v1.0.int8.onnx` and `voices-v1.0.bin` from the kokoro-onnx GitHub release
`model-files-v1.0` into `.tts/models/`, then:

```bash
.tts\Scripts\python tts/kokoro_say.py af_heart scripts/promo.json public/audio/promo
```

```bash
.tts\Scripts\python tts/kokoro_say.py af_heart scripts/tech.json public/audio/tech
```

```bash
.tts\Scripts\python tts/make_sound.py
```

```bash
.tts\Scripts\python tts/make_beat.py
```

```bash
npm install
```

```bash
npm run render:promo
```

```bash
npm run render:tech
```

`npm run studio` opens Remotion Studio to preview and edit scenes. The narration lives in
`scripts/*.json`. Scene lengths follow the generated audio, so after changing a line, regenerate
its audio and the video adjusts.
