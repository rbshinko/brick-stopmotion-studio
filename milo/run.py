"""One command per episode.   python milo/run.py epNN STEP [args]
STEPS
  voice    Kokoro voice (af_heart 1.32x, +1.5 st) + faster-whisper word timings
  plan     shots, sound effects and music gaps from episodes/epNN.py (prints shot stats)
  stills   50% still from the middle of every shot + contact sheet work/epNN/stills/_sheet.png
  frames   full render (optional frame range A B)
  check    flags frames where nothing moves + every-3rd-frame contact sheets
  post     captions + mix + encode -> outbox/milo-epNN-<slug>-v1.mp4 (+ .txt description)
  all      voice plan frames check post   (use after the stills look right)
  prep     voice plan stills"""
import glob, json, os, re, subprocess, sys

MILO = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(MILO)
ENGINE = os.path.join(MILO, "engine")
# Tool paths come from config.json (written by `python setup.py`); these are the fallbacks used before it existed.
DEFAULTS = {
    "python": os.path.join(MILO, ".venv", "Scripts", "python.exe") if os.name == "nt"
    else os.path.join(MILO, ".venv", "bin", "python"),
    "blender": "blender",          # setup.py writes the real path into config.json
    "ffmpeg": "ffmpeg",
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(MILO, "config.json"), encoding="utf-8") as f:
            cfg.update({k: v for k, v in json.load(f).items() if v})
    except (OSError, ValueError):
        pass
    for k in ("python", "blender", "ffmpeg"):          # paths inside the project are stored relative to milo/
        if os.sep in cfg[k] or "/" in cfg[k]:
            cfg[k] = os.path.normpath(os.path.join(MILO, cfg[k]))
    return cfg


CFG = load_config()
PY, BLENDER = CFG["python"], CFG["blender"]


def faces_dir():
    look = os.environ.get("MILO_LOOK")
    return "faces_" + look if look in ("real", "brick") else "faces"


def tool_env():
    """The engine scripts call plain `ffmpeg`; put the configured one first on PATH."""
    env = dict(os.environ, MILO_EP=EP, PYTHONIOENCODING="utf-8")
    ff = os.path.dirname(CFG["ffmpeg"])
    if ff:
        env["PATH"] = ff + os.pathsep + env.get("PATH", "")
    return env


def need(path, what):
    if not os.path.exists(path):
        sys.exit(f"{what} not found at {path}\nRun `python setup.py` in {MILO} once to install it.")


def sh(cmd, quiet_blender=False):
    need(cmd[0], "Blender" if quiet_blender else "The engine's Python (.venv)")
    env = tool_env()
    if quiet_blender:
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        for line in (p.stdout + p.stderr).splitlines():
            if re.search(r"built |Error|Traceback|line \d+|Exception", line):
                print(line)
        if p.returncode or "Traceback" in p.stdout + p.stderr:
            sys.exit(p.returncode or 1)
    else:
        subprocess.run(cmd, env=env, check=True, cwd=ENGINE)


def blender(mode, out, *args):
    sh([BLENDER, "-b", "--factory-startup", "--python", os.path.join(ENGINE, "build.py"), "--", mode, out, *args],
       quiet_blender=True)


def sheet(files, dst, cols=6, w=180, h=320):
    from PIL import Image, ImageDraw
    rows = (len(files) + cols - 1) // cols
    im = Image.new("RGB", (cols * w, rows * (h + 14)), "white")
    d = ImageDraw.Draw(im)
    for i, f in enumerate(files):
        x, y = (i % cols) * w, (i // cols) * (h + 14)
        im.paste(Image.open(f).convert("RGB").resize((w, h)), (x, y))
        d.text((x + 2, y + h), os.path.basename(f)[:-4][:28], fill="black")
    im.save(dst)
    print("sheet:", dst)


def slug():
    sys.path.insert(0, os.path.join(MILO, "episodes"))
    from season1 import EPISODES
    t = re.sub(r"[^a-z0-9]+", "-", EPISODES[EP]["title"].lower()).strip("-")
    return f"milo-{EP}-{t[:40].strip('-')}"


def step(name, *args):
    work = os.path.join(MILO, "work", EP)
    if name == "voice":
        if not os.path.exists(os.path.join(MILO, "work", faces_dir(), "atlas.png")):
            sh([PY, "faces.py"])
        if not os.path.exists(os.path.join(MILO, "work", "prints", "atlas.png")):
            sh([PY, "prints.py"])
        sh([PY, "voice.py"])
        sh([PY, "align.py"])
    elif name == "plan":
        sh([PY, "plan.py"])
    elif name == "stills":
        sh([PY, "plan.py"])                 # staging edits always re-plan first
        out = os.path.join(work, "stills")
        for f in glob.glob(os.path.join(out, "*.png")):
            os.remove(f)
        blender("stills", out, *args)
        sheet(sorted(f for f in glob.glob(os.path.join(out, "*.png")) if "_sheet" not in f),
              os.path.join(out, "_sheet.png"))
    elif name == "frames":
        blender("frames", os.path.join(work, "frames"), *args)
    elif name == "check":
        sh([PY, "check.py"])
    elif name == "post":
        os.makedirs(os.path.join(ROOT, "outbox"), exist_ok=True)
        sh([PY, "post.py", os.path.join(ROOT, "outbox", slug() + "-" + os.environ.get("MILO_VER", "v2") + ".mp4")])
    elif name == "meta":                  # rewrite the .txt only (title, description, pinned comment)
        sh([PY, "post.py", os.path.join(ROOT, "outbox", slug() + "-" + os.environ.get("MILO_VER", "v2") + ".mp4"),
            "--meta-only"])
    elif name in ("all", "prep"):
        seq = ["voice", "plan", "frames", "check", "post"] if name == "all" else ["voice", "plan", "stills"]
        for s in seq:
            print(f"== {EP} {s}", flush=True)
            step(s)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    EP = sys.argv[1]
    step(sys.argv[2], *sys.argv[3:])
