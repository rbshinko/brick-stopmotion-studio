# Install the Milo story-Shorts engine (once)

You install once, then make as many videos as you like. Everything goes inside this `milo/` folder:
nothing global changes and you never need admin rights.

## What you need first

- **Windows 10/11** (macOS and Linux work on a best-effort basis, see below)
- **Python 3.12** from https://www.python.org/downloads/ (tick "Add python.exe to PATH")
- A graphics card with an up-to-date driver (Blender's Eevee renderer needs OpenGL 4.3)
- About **6 GB** of free disk space and an internet connection for the first run

## Install

Open a terminal in this `milo` folder (or ask Claude Code to do it) and run:

```
python setup.py --check     # shows what you have and what is missing; changes nothing
python setup.py             # installs only what is missing, then runs a short self-test
```

You get a checklist: `✓` already there, `⬇` installing now, `✗` failed (with a "how to fix" line),
`!` optional. Run it again any time: a second run finds everything and finishes in a few seconds.

| Item | Where it comes from | Where it goes |
|---|---|---|
| Blender 4.5 LTS (portable) | download.blender.org, SHA-256 checked | `milo/tools/blender-4.5.x-.../` (an existing 4.5 install is reused) |
| ffmpeg | your PATH, else the gyan.dev build linked from ffmpeg.org, SHA-256 checked | `milo/tools/ffmpeg/` |
| Python packages (`requirements.txt`) | PyPI | `milo/.venv/` (an existing one that works is reused) |
| Kokoro voice model (350 MB) | kokoro-onnx GitHub release, size and SHA-256 checked | `milo/assets/kokoro/` |
| Whisper model large-v3-turbo (1.6 GB) | Hugging Face | your Hugging Face cache |
| Surface textures | Poly Haven (CC0) via `engine/textures.py` | `milo/assets/textures/` |
| Face and shirt-print images | drawn locally by `engine/faces.py` / `prints.py` | `milo/work/faces*/`, `milo/work/prints/` |
| Open-licence sounds | their authors' sites, SHA-256 checked | `my-sounds/` (see below) |

The self-test renders a tiny Eevee frame, speaks "Hi, I am Milo." with Kokoro and finds the word
timings with Whisper. It runs once, and again only when a tool changes (or with `--selftest`).

`setup.py` writes `milo/config.json` with the tool paths; `run.py` reads it. It holds no keys or
passwords. To use a Blender you already have, set `MILO_BLENDER` to its `blender.exe` before setup.

## Make your first video

```
.venv\Scripts\python.exe run.py ep01 prep      # voice + plan + still frames (check stills/_sheet.png)
.venv\Scripts\python.exe run.py ep01 all       # full render, check and final edit -> ../outbox/
```

(macOS/Linux: `.venv/bin/python`.) Set `MILO_LOOK=real` or `MILO_LOOK=brick` for the other looks.

## Sound effects

The channel's sound palette (`engine/palette.py`) reads files from the `my-sounds/` folder next to
`milo/`. Most of it can be downloaded for you; some of it cannot be shared:

| Sounds | Source | Licence | setup.py |
|---|---|---|---|
| pop1, pop2, sparkle, whoosh, whoosh2, impact, boing, zip, snip, ding, doorbell, knock, sting | github.com/wyzowl/sfx-kit | CC0 | downloads them |
| chicken | Meta Open Sound, Oculus Audio Pack | CC BY 4.0 (credit added to the description automatically) | downloads it |
| music "island" | "Feel good island" by HaelDB, opengameart.org/node/4797 | CC0 | downloads it |
| music "riley" | "Life of Riley", Kevin MacLeod, incompetech.com | CC BY 4.0 (credit added automatically) | downloads it |
| gasp, cough, laugh, whistle, squeak, crack, growl, bubbles, dizzy | Sonniss GDC 2026 Game Audio Bundle | free, but the files may not be shared | **you add them** |
| slap | the channel owner's own recording | not shipped | **you add it** |

**If a sound is missing, the `post` step stops** with an ffmpeg error for any episode whose plan uses
it (`engine/post.py` decodes every planned sound and does not skip missing files). Everything before
`post` (voice, plan, stills, frames) works without any sounds. Your options:

1. **Get the free Sonniss bundle** from https://sonniss.com/gameaudiogdc and unpack it so the files sit
   at the paths listed in `engine/palette.py` under `my-sounds/sfx/gdc26/Sonniss.com-GDC2026-GameAudioBundle/`.
2. **Drop in your own CC0 sounds**: save any short `.wav`/`.ogg`/`.mp3` at the exact path and file name
   that `engine/palette.py` expects for that sound name (for example a CC0 gasp from
   https://opengameart.org or https://sonniss.com). The file only has to exist; length and level are
   trimmed and normalised automatically.
3. **Point the palette at your own files**: change the path for that name in `engine/palette.py`.

`python setup.py` lists which sounds are still missing each time you run it.
