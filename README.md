# Brick Stop-Motion Studio

Make vertical (1080×1920) story Shorts in a **toy-brick stop-motion style** with Claude Code: brick-built
sets, original brick figures, motion that steps like real stop motion, a kid narrator, captions, sound and a
YouTube title and description. Everything is built in Blender from code, on your own PC, with free tools.

The stories follow one format: *"In this town, if you ___, you ___."* You pick an idea, approve the script,
and the engine renders the video.

> Not affiliated with or endorsed by the LEGO Group. This project uses its own original brick figures and
> never uses the LEGO name or logo. Please keep it that way in your videos.

## Install (once)

You need [Claude Code](https://claude.com/claude-code) and Python 3.11+.
Windows works best; macOS and Linux are best effort. A GPU is recommended (an RTX 3060 or similar).

1. Download this repo (Code → Download ZIP, or `git clone`), and open the folder in Claude Code.
2. Paste this prompt into Claude Code:

```
Set up this project: run "python milo/setup.py" and fix anything it reports, then tell me when it's ready.
```

`setup.py` checks what you already have and installs only what's missing, all inside the project folder:
Blender 4.5 LTS, ffmpeg, the Python packages, the Kokoro voice, the whisper timing model, CC0 textures and
some free sounds. It finishes with a small test render. Running it again is safe and fast.
See [milo/INSTALL.md](milo/INSTALL.md) for details and fixes.

## Make a video

In Claude Code, say for example:

```
Make a brick stop-motion video
```

The `brick-stopmotion` skill takes over:
1. It asks one or two questions first (your cast, how many videos).
2. It gives you 5 episode ideas to pick from.
3. It shows you the script, and doesn't make the voice until you approve it.
4. The first time, it runs a look test (3 stills and a 3-second clip) so you can pick the style.
5. It renders the video to `outbox/`, with a `.txt` file next to it holding the title, description and
   pinned comment.

A 30–35 s video takes about 20–35 minutes of rendering on a mid-range GPU. Rendering uses your PC, not
your Claude usage.

## What's inside

| Path | What it is |
|---|---|
| `.claude/skills/brick-stopmotion/`, `.agents/skills/brick-stopmotion/` | The skill: the workflow, story recipe and look rules |
| `milo/setup.py`, `milo/INSTALL.md` | The one-time installer and its guide |
| `milo/run.py` | One command per step: `voice`, `plan`, `stills`, `frames`, `check`, `post`, `meta` |
| `milo/engine/` | The Blender engine: rig, sets, brick kit, looks, props, captions and mix |
| `milo/episodes/` | An example brick episode (EP11, "If you shout, your head pops off") |
| `milo/docs/STORY-RECIPE.md` | The pacing and writing recipe |
| `milo/STAGING.md` | How to stage an episode: poses, props and shot types |

Your own sounds go in a `my-sounds/` folder next to `milo/`. Any sound that isn't installed is skipped,
so the video still renders.

## Licenses

- Code: MIT (see [LICENSE](LICENSE)).
- Montserrat font: SIL Open Font License 1.1.
- Textures: CC0 from Poly Haven, downloaded by setup.
- Voice model: Kokoro (Apache 2.0).
- Some sounds and music need a credit. The engine writes it into each video's `.txt` file automatically.
