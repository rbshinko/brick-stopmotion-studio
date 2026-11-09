"""One-time installer for the Milo story-Shorts engine.   Run it from anywhere:

    python setup.py              check everything, install only what is missing, then self-test
    python setup.py --check      report only: change nothing, download nothing
    python setup.py --selftest   also re-run the self-test even if it passed before

Everything goes inside this folder (milo/tools, milo/.venv, milo/assets, milo/work), so nothing global
changes and no admin rights are needed. Downloads come only from official sources (download.blender.org,
the ffmpeg builds linked from ffmpeg.org, PyPI, Hugging Face, the Kokoro-ONNX GitHub release, Poly Haven,
and the original sound authors) and are checked against a SHA-256 or size where one is published.
Safe to re-run: a second run finds everything and finishes in seconds. Writes milo/config.json for run.py.
Windows first; macOS and Linux are best effort with clear messages."""
import argparse, glob, hashlib, importlib.util, json, os, platform, re, shutil, ssl, subprocess, sys
import tarfile, tempfile, time, urllib.parse, urllib.request, zipfile

MILO = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(MILO)
ENGINE = os.path.join(MILO, "engine")
TOOLS = os.path.join(MILO, "tools")
CONFIG = os.path.join(MILO, "config.json")
WIN, MAC = os.name == "nt", sys.platform == "darwin"
ARM = platform.machine().lower() in ("arm64", "aarch64")
VENV = os.path.join(MILO, ".venv")
VPY = os.path.join(VENV, "Scripts", "python.exe") if WIN else os.path.join(VENV, "bin", "python")
UA = {"User-Agent": "milo-setup/1.0"}

BLENDER_SERIES = "4.5"                       # Blender 4.5 LTS
BLENDER_FALLBACK = "4.5.15"                  # used only if the release listing can't be read
BLENDER_DL = "https://download.blender.org/release/Blender4.5/"
WHISPER = "large-v3-turbo"                   # what engine/align.py loads
KOKORO_DIR = os.path.join(MILO, "assets", "kokoro")
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO = {  # file: (bytes, sha256) of the official v1.0 release files that engine/voice.py loads
    "kokoro-v1.0.onnx": (325532387, "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5"),
    "voices-v1.0.bin": (28214398, "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"),
}
IMPORTS = "import kokoro_onnx, faster_whisper, numpy, PIL, soundfile, av"
LOOKS = [("brand", None, "faces"), ("real", "real", "faces_real"), ("brick", "brick", "faces_brick")]

# Sounds the palette uses that have a public, official source we may download from (pinned commits/hashes).
SFX_KIT = "https://raw.githubusercontent.com/wyzowl/sfx-kit/92780e7ab0cdfb557497a988089c47f46e8c7412/"
META = "https://raw.githubusercontent.com/facebookincubator/Meta-open-sound/251c0be57d5d1b3242b91f53e0cde62ab1cb42d9/"
SOUND_SHA = {
    "pop-small-in.wav": "917759c812aff57bca97627a3c89c7aa5f1b4be7c9494a352cd6ba1dc0984769",
    "pop-medium-in.wav": "0c92cb9be01b1b5a3b51d4a6bfe427947b228ea71bb95d5a0b6c8641b7eab511",
    "shimmer-short-sparkle.wav": "e0a5e97ece9d4787bb6bd50fd88546d673f96c4b46938de0fb82b43b24b28af5",
    "swish-medium.wav": "41a97a849f311cdb0da2de185386fc88e74db2df54d214bc8d9ff931b5e83c9c",
    "swish-soft.wav": "c18c581c43ac848b10c946e2a3c402b79370d99b057c2399b832d39f9d9236ab",
    "impact-deep-firm.wav": "43ebc44857bab1899524e37eb3b5ed7cf2c564a4a1343c1114ca58185a64446e",
    "move-spring.wav": "c850f6e89bebd99ed63f632190ef3ec7d06650263d7cd6aaa61d98c4e2e12076",
    "zip-in-hard.wav": "cc7ac891e6c5859ded16b886445e2891aad0067a8fce5c53e1153c661eccd219",
    "props-scissors.wav": "748f90fdc649bce100907306363017aa8444b2779c3ad767cc74af829c9dd7d1",
    "tone-ding-high.wav": "4a77d6a7a7d10956997e9bf8353fc1aaa6bb5f191f5e1ffbb36c33471b162f92",
    "props-doorbell.wav": "cefafff280250b93e9b51b53235320cb08f6aa046928d5253761b35e21b0ece1",
    "notification-failure-knock.wav": "12b1ef87204233247ae2226e21fe9c2e25efa0c7e1eba55c407bc8c61015f04b",
    "sting-warm-long.wav": "22140cc3ce2394a6d58b13b4f302dfe91789cb397c18407288ff040fa459aca4",
    "BIRDFowl_Chicken_OS_01.ogg": "a34441f0792e6eef21e8a8660fb39f0d96c5d780d8863509e67bbe0745be07c5",
    "island_0.ogg": "e8e5a246faa95cdb7bb86fa7c62edfc4636749cabe83d158f43bd62c366cdc9d",
    "Life of Riley.mp3": "1916f05cd1860949f9241e17966d334c39852b531329e4a05802720bb154c564",
}

OK, GET, BAD, WARN = "\u2713", "\u2b07", "\u2717", "!"
problems, notes = [], []


def say(mark, what, detail=""):
    print(f"  {mark} {what:<22} {detail}".rstrip(), flush=True)


def fail(what, detail, fix):
    say(BAD, what, detail)
    print(f"      how to fix: {fix}", flush=True)
    problems.append(what)


# ---------------------------------------------------------------- helpers
def run(cmd, timeout=600, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, **kw)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def rel(p):
    """Paths inside milo/ are stored relative, so the folder can be moved."""
    p = os.path.abspath(p)
    return os.path.relpath(p, MILO) if p.startswith(MILO + os.sep) else p


def absmilo(p):
    return os.path.normpath(os.path.join(MILO, p)) if p else p


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _open(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            raise
        try:                                   # some Pythons ship without CA roots; certifi has them
            import certifi
        except ImportError:
            raise RuntimeError("this Python can't verify HTTPS certificates. Install Python from "
                               "python.org (tick 'Install certificates' on macOS) and try again") from e
        return urllib.request.urlopen(req, timeout=timeout,
                                      context=ssl.create_default_context(cafile=certifi.where()))


def fetch_text(url):
    with _open(url, 30) as r:
        return r.read().decode("utf-8", "replace")


def download(url, dst, sha=None, size=None):
    """Stream url -> dst (via dst.part), verify size/sha256, then move into place."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    part = dst + ".part"
    with _open(url, 120) as r, open(part, "wb") as f:
        total, done, shown = int(r.headers.get("Content-Length") or 0), 0, -1
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            done += len(b)
            if total > 20 << 20 and int(done * 10 / total) != shown:
                shown = int(done * 10 / total)
                print(f"      {done >> 20} / {total >> 20} MB", flush=True)
    if size and os.path.getsize(part) != size:
        os.remove(part)
        raise RuntimeError(f"size mismatch for {os.path.basename(dst)} (got {os.path.getsize(part)}, want {size})")
    if sha and sha256(part).lower() != sha.lower():
        os.remove(part)
        raise RuntimeError(f"checksum mismatch for {os.path.basename(dst)}: the download is damaged or changed")
    os.replace(part, dst)
    return dst


def free_gb(path=MILO):
    return shutil.disk_usage(path).free / 1e9


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def read_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- Blender
def blender_version(exe):
    if not exe or not os.path.isfile(exe):
        return None
    m = re.search(r"Blender (\d+\.\d+\.\d+)", run([exe, "--version"], timeout=60).stdout)
    return m.group(1) if m else None


def blender_candidates(cfg):
    home = os.path.expanduser("~")
    c = [os.environ.get("MILO_BLENDER"), absmilo(cfg.get("blender"))]
    try:                                       # whatever run.py was already using keeps being used
        c.append(load_module("milo_run", os.path.join(MILO, "run.py")).DEFAULTS["blender"])
    except Exception:
        pass
    if WIN:
        exe = "blender.exe"
        pats = [os.path.join(TOOLS, "blender-4.5*", exe), os.path.join(home, "tools", "blender-4.5*", exe),
                os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Blender Foundation", "Blender 4.5", exe),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Blender Foundation", "Blender 4.5", exe),
                os.path.join(home, "Downloads", "blender-4.5*", exe), os.path.join(home, "Desktop", "blender-4.5*", exe),
                r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"]
    elif MAC:
        pats = [os.path.join(TOOLS, "Blender*.app", "Contents", "MacOS", "Blender"),
                "/Applications/Blender.app/Contents/MacOS/Blender",
                os.path.join(home, "Applications", "Blender.app", "Contents", "MacOS", "Blender")]
    else:
        pats = [os.path.join(TOOLS, "blender-4.5*", "blender"), os.path.join(home, "blender-4.5*", "blender"),
                os.path.join(home, "tools", "blender-4.5*", "blender"), "/opt/blender*/blender", "/snap/bin/blender"]
    c.append(shutil.which("blender"))
    for p in pats:
        c += sorted(glob.glob(p), reverse=True)
    seen = []
    for p in c:
        if p and p not in seen:
            seen.append(p)
    return seen


def install_blender():
    try:
        listing = fetch_text(BLENDER_DL)
        vers = sorted({tuple(map(int, v)) for v in re.findall(r"blender-4\.5\.(\d+)\.sha256", listing)})
        ver = f"4.5.{vers[-1][0]}" if vers else BLENDER_FALLBACK
    except Exception:
        ver = BLENDER_FALLBACK
    arch = "arm64" if ARM else "x64"
    name = (f"blender-{ver}-windows-{arch}.zip" if WIN else f"blender-{ver}-macos-{arch}.dmg" if MAC
            else f"blender-{ver}-linux-x64.tar.xz")
    sums = fetch_text(f"{BLENDER_DL}blender-{ver}.sha256")
    m = re.search(r"([0-9a-f]{64})\s+" + re.escape(name), sums)
    if not m:
        raise RuntimeError(f"no official checksum for {name}")
    if free_gb() < 2.5:
        raise RuntimeError(f"only {free_gb():.1f} GB free; Blender needs about 2.5 GB")
    say(GET, "Blender", f"downloading {name} from download.blender.org")
    with tempfile.TemporaryDirectory(dir=MILO) as tmp:
        arc = download(BLENDER_DL + name, os.path.join(tmp, name), sha=m.group(1))
        say(" ", "", "checksum OK, unpacking")
        os.makedirs(TOOLS, exist_ok=True)
        if WIN:
            with zipfile.ZipFile(arc) as z:     # \\?\ prefix: Blender's add-on paths can pass 260 chars
                z.extractall("\\\\?\\" + TOOLS)
            return os.path.join(TOOLS, name[:-4], "blender.exe")
        if MAC:
            mnt = os.path.join(tmp, "mnt")
            r = run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", mnt, arc])
            if r.returncode:
                raise RuntimeError("could not open the .dmg: " + r.stderr.strip())
            try:
                dst = os.path.join(TOOLS, f"Blender-{ver}.app")
                shutil.copytree(os.path.join(mnt, "Blender.app"), dst, symlinks=True)
            finally:
                run(["hdiutil", "detach", mnt])
            return os.path.join(dst, "Contents", "MacOS", "Blender")
        with tarfile.open(arc) as t:
            t.extractall(TOOLS)
        return os.path.join(TOOLS, name[:-7], "blender")


def step_blender(cfg, check):
    for exe in blender_candidates(cfg):
        v = blender_version(exe)
        if v and v.startswith(BLENDER_SERIES + "."):
            say(OK, "Blender", f"{v} LTS  {exe}")
            return exe, v
        if v:
            notes.append(f"Ignored Blender {v} at {exe} (the engine is built for {BLENDER_SERIES} LTS).")
    if check:
        say(GET, "Blender", f"{BLENDER_SERIES} LTS not found: would download it (about 400 MB) into tools/")
        problems.append("Blender")
        return None, None
    try:
        exe = install_blender()
        v = blender_version(exe)
        if not v:
            raise RuntimeError("unpacked, but it does not start")
        say(OK, "Blender", f"{v} LTS installed  {exe}")
        return exe, v
    except Exception as e:
        fail("Blender", str(e), f"download Blender {BLENDER_SERIES} LTS (portable .zip) from "
             "https://www.blender.org/download/lts/4-5/ , unpack it into milo/tools/ and run setup again "
             "(or set MILO_BLENDER to its blender.exe)")
        return None, None


# ---------------------------------------------------------------- ffmpeg
def ffmpeg_ok(exe):
    if not exe or not (os.path.isfile(exe) or shutil.which(exe)):
        return None
    m = re.search(r"ffmpeg version (\S+)", run([exe, "-version"], timeout=30).stdout)
    return m.group(1) if m else None


def install_ffmpeg():
    if WIN:   # gyan.dev release build (linked from ffmpeg.org/download.html), with its published sha256
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        sha = fetch_text(url + ".sha256").split()[0]
    elif MAC:
        raise RuntimeError("no portable macOS build is installed automatically")
    else:     # BtbN static build (linked from ffmpeg.org/download.html), checked against its checksums file
        name = f"ffmpeg-master-latest-{'linuxarm64' if ARM else 'linux64'}-gpl.tar.xz"
        base = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        m = re.search(r"([0-9a-f]{64})\s+\*?" + re.escape(name), fetch_text(base + "checksums.sha256"))
        url, sha = base + name, m.group(1) if m else None
    say(GET, "ffmpeg", "downloading " + url)
    dst = os.path.join(TOOLS, "ffmpeg")
    with tempfile.TemporaryDirectory(dir=MILO) as tmp:
        arc = download(url, os.path.join(tmp, os.path.basename(url)), sha=sha)
        shutil.rmtree(dst, ignore_errors=True)
        if arc.endswith(".zip"):
            with zipfile.ZipFile(arc) as z:
                z.extractall(dst)
        else:
            with tarfile.open(arc) as t:
                t.extractall(dst)
    exe = glob.glob(os.path.join(dst, "*", "bin", "ffmpeg.exe" if WIN else "ffmpeg"))
    if not exe:
        raise RuntimeError("unpacked, but ffmpeg was not inside")
    return exe[0]


def step_ffmpeg(cfg, check):
    pats = [os.path.join(TOOLS, "ffmpeg", "*", "bin", "ffmpeg.exe" if WIN else "ffmpeg")]
    cands = [absmilo(cfg.get("ffmpeg")), shutil.which("ffmpeg")] + glob.glob(pats[0])
    if MAC:
        cands += ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
    for exe in cands:
        v = ffmpeg_ok(exe)
        if v:
            exe = os.path.abspath(shutil.which(exe) or exe)
            say(OK, "ffmpeg", f"{v}  {exe}")
            return exe
    if check:
        say(GET, "ffmpeg", "not found: would download a portable build (about 100 MB) into tools/")
        problems.append("ffmpeg")
        return None
    try:
        exe = install_ffmpeg()
        say(OK, "ffmpeg", f"{ffmpeg_ok(exe)} installed  {exe}")
        return exe
    except Exception as e:
        fail("ffmpeg", str(e), "macOS: `brew install ffmpeg`. Linux: `sudo apt install ffmpeg` (or your distro's "
             "package). Windows: get the 'release essentials' zip from https://www.gyan.dev/ffmpeg/builds/ and "
             "unpack it into milo/tools/ffmpeg/. Then run setup again.")
        return None


# ---------------------------------------------------------------- Python env
def venv_ok():
    if not os.path.exists(VPY):
        return False, "milo/.venv not found"
    r = run([VPY, "-c", IMPORTS], timeout=180)
    return r.returncode == 0, (r.stderr.strip().splitlines() or ["?"])[-1]


def step_venv(check):
    ok, why = venv_ok()
    if ok:
        say(OK, "Python packages", f"milo/.venv  {VPY}")
        return True
    if check:
        say(GET, "Python packages", f"{why}: would install requirements.txt into milo/.venv")
        problems.append("Python packages")
        return False
    if sys.version_info < (3, 10) or sys.version_info >= (3, 14):
        notes.append(f"You are running Python {platform.python_version()}; the engine is tested on 3.12. "
                     "If the install fails, install Python 3.12 from python.org and run setup with it.")
    try:
        if not os.path.exists(VPY):
            say(GET, "Python packages", "creating milo/.venv")
            r = run([sys.executable, "-m", "venv", VENV], timeout=600)
            if r.returncode:
                raise RuntimeError(r.stderr.strip()[-400:])
        say(GET, "Python packages", "installing requirements.txt (about 700 MB, a few minutes)")
        r = subprocess.run([VPY, "-m", "pip", "install", "--disable-pip-version-check", "-q",
                            "-r", os.path.join(MILO, "requirements.txt")])
        if r.returncode:
            raise RuntimeError("pip install failed (see the messages above)")
        ok, why = venv_ok()
        if not ok:
            raise RuntimeError(why)
        say(OK, "Python packages", "installed into milo/.venv")
        return True
    except Exception as e:
        fail("Python packages", str(e), "install Python 3.12 from https://www.python.org/downloads/ "
             "(Windows: tick 'Add python.exe to PATH'), delete milo/.venv, and run `python setup.py` again")
        return False


# ---------------------------------------------------------------- models
def step_kokoro(check):
    missing = [f for f, (size, _) in KOKORO.items()
               if not (os.path.exists(os.path.join(KOKORO_DIR, f)) and os.path.getsize(os.path.join(KOKORO_DIR, f)) == size)]
    if not missing:
        say(OK, "Kokoro voice model", rel(KOKORO_DIR))
        return True
    if check:
        say(GET, "Kokoro voice model", f"would download {', '.join(missing)} (about 350 MB)")
        problems.append("Kokoro voice model")
        return False
    try:
        for f in missing:
            say(GET, "Kokoro voice model", f"downloading {f} from the kokoro-onnx GitHub release")
            size, sha = KOKORO[f]
            download(KOKORO_URL + f, os.path.join(KOKORO_DIR, f), sha=sha, size=size)
        say(OK, "Kokoro voice model", "downloaded and checksum OK")
        return True
    except Exception as e:
        fail("Kokoro voice model", str(e), f"download kokoro-v1.0.onnx and voices-v1.0.bin from "
             f"https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0 into {KOKORO_DIR}")
        return False


def step_whisper(have_venv, check):
    if not have_venv:
        fail("Whisper model", "skipped", "fix the Python packages first")
        return False
    probe = f"from faster_whisper.utils import download_model as d; print(d({WHISPER!r}, local_files_only=True))"
    r = run([VPY, "-c", probe], timeout=180)
    if r.returncode == 0:
        say(OK, "Whisper model", f"{WHISPER} (Hugging Face cache)")
        return True
    if check:
        say(GET, "Whisper model", f"would download faster-whisper {WHISPER} (about 1.6 GB)")
        problems.append("Whisper model")
        return False
    say(GET, "Whisper model", f"downloading faster-whisper {WHISPER} from Hugging Face (about 1.6 GB)")
    r = subprocess.run([VPY, "-c", probe.replace("local_files_only=True", "local_files_only=False")])
    if r.returncode:
        fail("Whisper model", "download failed", "check your internet connection and run setup again")
        return False
    say(OK, "Whisper model", "downloaded")
    return True


# ---------------------------------------------------------------- textures, atlases
def step_textures(have_venv, check):
    tex = load_module("milo_textures", os.path.join(ENGINE, "textures.py"))
    missing = sorted({tex.TEX[r][0] for r in tex.TEX for p in tex.paths(r).values() if not os.path.exists(p)})
    if not missing:
        say(OK, "CC0 textures", f"{len(tex.TEX)} Poly Haven sets in assets/textures")
        return True
    if check or not have_venv:
        say(GET, "CC0 textures", f"would download {len(missing)} Poly Haven sets ({', '.join(missing[:4])}...)")
        problems.append("CC0 textures")
        return False
    say(GET, "CC0 textures", f"downloading {len(missing)} sets from Poly Haven (CC0)")
    r = run([VPY, os.path.join(ENGINE, "textures.py")], timeout=1800, cwd=ENGINE)
    still = [p for rl in tex.TEX for p in tex.paths(rl).values() if not os.path.exists(p)]
    if r.returncode or still:
        fail("CC0 textures", (r.stderr.strip().splitlines() or ["incomplete"])[-1],
             "check your internet connection and run setup again (polyhaven.com must be reachable)")
        return False
    say(OK, "CC0 textures", "downloaded")
    return True


def step_atlases(have_venv, check):
    faces_src = open(os.path.join(ENGINE, "faces.py"), encoding="utf-8").read()
    todo, skipped = [], []
    for look, env, d in LOOKS:
        if look == "brick" and "brick" not in faces_src:
            skipped.append(look)       # this engine version has no brick faces yet
            continue
        if not os.path.exists(os.path.join(MILO, "work", d, "atlas.png")):
            todo.append(("faces.py", look, env, d))
    if not os.path.exists(os.path.join(MILO, "work", "prints", "atlas.png")):
        todo.append(("prints.py", "real", "real", "prints"))
    looks = [l for l, _, _ in LOOKS if l not in skipped]
    if skipped:
        looks.append(f"({', '.join(skipped)}: not in this engine version yet)")
    if not todo:
        say(OK, "Face/print atlases", f"looks: {', '.join(looks)}")
        return True
    names = ", ".join(f"work/{d}" for _, _, _, d in todo)
    if check or not have_venv:
        say(GET, "Face/print atlases", f"would draw {names}")
        problems.append("Face/print atlases")
        return False
    say(GET, "Face/print atlases", f"drawing {names}")
    for script, look, env, d in todo:
        e = {k: v for k, v in os.environ.items() if k != "MILO_LOOK"}
        if env:
            e["MILO_LOOK"] = env
        r = run([VPY, script], timeout=600, cwd=ENGINE, env=e)
        if r.returncode or not os.path.exists(os.path.join(MILO, "work", d, "atlas.png")):
            fail("Face/print atlases", f"{script} ({look}) failed: " + (r.stderr.strip().splitlines() or ["?"])[-1],
                 f"run `MILO_LOOK={env or ''} .venv python engine/{script}` from milo/engine to see the error")
            return False
    say(OK, "Face/print atlases", f"looks: {', '.join(looks)}")
    return True


# ---------------------------------------------------------------- sounds
def sound_source(relpath):
    """Official public URL for a palette sound, or None if it comes from a library that can't be shared."""
    p = relpath.replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    q = urllib.parse.quote
    if p.startswith("sfx/sfx-kit/"):
        return SFX_KIT + q(p[len("sfx/sfx-kit/"):]), "sfx-kit (CC0)"
    if p.startswith("sfx/Meta-open-sound/"):
        return META + q(p[len("sfx/Meta-open-sound/"):]), "Meta Open Sound / Oculus Audio Pack (CC BY 4.0)"
    if p.startswith("music/incompetech/"):
        return "https://incompetech.com/music/royalty-free/mp3-royaltyfree/" + q(name), "incompetech (CC BY 4.0)"
    if name == "island_0.ogg":   # "Feel good island" by HaelDB, opengameart.org/node/4797 (CC0 / OGA-BY 3.0)
        return "https://opengameart.org/sites/default/files/island_0.ogg", "OpenGameArt (CC0)"
    return None


def step_sounds(check):
    try:
        pal = load_module("milo_palette", os.path.join(ENGINE, "palette.py"))
    except Exception as e:
        say(WARN, "Sounds", f"could not read engine/palette.py: {e}")
        return
    items = [(k, r) for k, (r, _) in pal.SFX.items()] + [(k, r) for k, (r, _) in pal.MUSIC.items()]
    missing = [(k, r) for k, r in items if not os.path.exists(pal.path(r))]
    if not missing:
        say(OK, "Sounds", f"all {len(items)} palette sounds found in {pal.SOUNDS}")
        return
    open_, private = [(k, r) for k, r in missing if sound_source(r)], [k for k, r in missing if not sound_source(r)]
    if open_ and check:
        say(GET, "Sounds", f"would fetch {len(open_)} open-licence sounds: {', '.join(k for k, _ in open_)}")
    elif open_:
        say(GET, "Sounds", f"fetching {len(open_)} open-licence sounds from their authors")
        for k, r in open_:
            url, src = sound_source(r)
            try:
                download(url, pal.path(r), sha=SOUND_SHA.get(r.replace("\\", "/").rsplit("/", 1)[-1]))
            except Exception as e:
                private.append(k)
                notes.append(f"Sound '{k}' from {src} failed: {e}")
    if private:
        say(WARN, "Sounds", f"{len(private)} of {len(items)} need your own sound library: {', '.join(private)}")
        print("      These come from the Sonniss GDC bundle (free, but its licence forbids sharing the files) or\n"
              "      the channel owner's own recordings. Episodes that use them stop at the `post` step until\n"
              "      you add a file at the same path under my-sounds/. See INSTALL.md > Sound effects.", flush=True)
    else:
        say(OK, "Sounds", f"all {len(items)} palette sounds ready")


# ---------------------------------------------------------------- self-test
EEVEE_TEST = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
sc = bpy.context.scene
for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        sc.render.engine = e
        break
    except TypeError:
        pass
sc.render.resolution_x = sc.render.resolution_y = 96
sc.render.resolution_percentage = 100
try:
    sc.eevee.taa_render_samples = 4
except AttributeError:
    pass
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
px = list(bpy.data.images.load(out).pixels)
print("MILO_EEVEE_OK", sc.render.engine, round(max(px[0::4]) - min(px[0::4]), 3))
'''

TTS_TEST = r'''
import sys, soundfile as sf
from kokoro_onnx import Kokoro
k = Kokoro(sys.argv[1], sys.argv[2])
y, sr = k.create("Hi, I am Milo.", voice="af_heart", speed=1.32, lang="en-us")
sf.write(sys.argv[3], y, sr)
print("MILO_TTS_OK %.2f" % (len(y) / sr))
'''

ALIGN_TEST = r'''
import subprocess, sys, numpy as np
from faster_whisper import WhisperModel
raw = subprocess.run([sys.argv[1], "-loglevel", "error", "-i", sys.argv[2], "-ac", "1", "-ar", "16000",
                      "-f", "f32le", "-"], check=True, capture_output=True).stdout
segs, _ = WhisperModel(sys.argv[3], device="cpu", compute_type="int8").transcribe(
    np.frombuffer(raw, np.float32), language="en", word_timestamps=True)
print("MILO_ALIGN_OK", " ".join("%s@%.2f" % (w.word.strip(), w.start) for s in segs for w in s.words))
'''

GPU_HINT = ("Eevee needs a working graphics driver (OpenGL 4.3). Update your GPU driver from NVIDIA/AMD/Intel. "
            "If it says 'GPU lost' or it worked before, reboot the PC (long renders can hang the driver). "
            "Remote desktops and virtual machines often have no GPU: run it on the PC itself.")


def selftest(blender, ffmpeg):
    print("\nSelf-test", flush=True)
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        if blender:
            script = os.path.join(tmp, "eevee_test.py")
            open(script, "w").write(EEVEE_TEST)
            t = time.time()
            r = run([blender, "-b", "--factory-startup", "--python", script, "--", os.path.join(tmp, "eevee.png")],
                    timeout=300)
            log = r.stdout + r.stderr
            if "MILO_EEVEE_OK" in log:
                say(OK, "Eevee render", f"96x96 test frame in {time.time() - t:.1f} s")
            else:
                gpu = re.search(r"GPU lost|OpenGL|EGL|GPU backend|unable to open a display|no GPU|Vulkan|"
                                r"GHOST|failed to create.*context|EXCEPTION_ACCESS_VIOLATION", log, re.I)
                lines = [l for l in log.splitlines() if re.search(r"error|gpu|opengl|exception", l, re.I)][-3:]
                fail("Eevee render", " | ".join(lines)[-300:] or f"Blender exited with code {r.returncode}",
                     GPU_HINT if gpu or r.returncode else "run setup again; if it repeats, reinstall Blender 4.5")
                ok = False
        if os.path.exists(VPY):
            wav = os.path.join(tmp, "hi.wav")
            r = run([VPY, "-c", TTS_TEST, os.path.join(KOKORO_DIR, "kokoro-v1.0.onnx"),
                     os.path.join(KOKORO_DIR, "voices-v1.0.bin"), wav], timeout=300)
            if "MILO_TTS_OK" in r.stdout:
                say(OK, "Kokoro voice", f"'Hi, I am Milo.' = {r.stdout.split('MILO_TTS_OK')[1].strip()} s")
                if ffmpeg:
                    r = run([VPY, "-c", ALIGN_TEST, ffmpeg, wav, WHISPER], timeout=600)
                    if "MILO_ALIGN_OK" in r.stdout:
                        say(OK, "Whisper alignment", r.stdout.split("MILO_ALIGN_OK")[1].strip()[:70])
                    else:
                        fail("Whisper alignment", (r.stderr.strip().splitlines() or ["?"])[-1][:200],
                             "run setup again; if it repeats, delete milo/.venv and run setup again")
                        ok = False
            else:
                fail("Kokoro voice", (r.stderr.strip().splitlines() or ["?"])[-1][:200],
                     "delete milo/assets/kokoro and run setup again")
                ok = False
    return ok


# ---------------------------------------------------------------- main
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="report only; change nothing")
    ap.add_argument("--selftest", action="store_true", help="re-run the self-test even if it passed before")
    a = ap.parse_args()
    cfg = read_config()
    print(f"Milo engine setup{' (check only)' if a.check else ''}  -  {MILO}\n", flush=True)
    if not (WIN or MAC):
        notes.append("Linux support is best effort.")
    elif MAC:
        notes.append("macOS support is best effort.")

    blender, bver = step_blender(cfg, a.check)
    ffmpeg = step_ffmpeg(cfg, a.check)
    have_venv = step_venv(a.check)
    step_kokoro(a.check)
    step_whisper(have_venv, a.check)
    step_textures(have_venv, a.check)
    step_atlases(have_venv, a.check)
    step_sounds(a.check)

    new = {"blender": rel(blender) if blender else cfg.get("blender"), "blender_version": bver,
           "ffmpeg": rel(ffmpeg) if ffmpeg else cfg.get("ffmpeg"), "python": rel(VPY),
           "whisper_model": WHISPER, "kokoro_dir": rel(KOKORO_DIR)}
    key = hashlib.sha1(json.dumps(new, sort_keys=True).encode()).hexdigest()[:12]
    last = cfg.get("selftest") or {}
    new["selftest"] = last
    if a.check:
        if last.get("ok") and last.get("key") == key:
            say(OK, "Self-test", f"passed on {last.get('date')}")
        else:
            say(WARN, "Self-test", "not run yet for these tools (run `python setup.py`)")
    else:
        if not problems and (a.selftest or not (last.get("ok") and last.get("key") == key)):
            passed = selftest(absmilo(new["blender"]), absmilo(new["ffmpeg"]))
            new["selftest"] = {"ok": passed, "key": key, "date": time.strftime("%Y-%m-%d %H:%M")}
        elif not problems:
            say(OK, "Self-test", f"passed on {last.get('date')} (--selftest to run it again)")
        if new != cfg:
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(new, f, indent=1)
            print(f"\n  wrote {CONFIG}", flush=True)

    for n in notes:
        print("  note: " + n)
    if problems:
        print(f"\n{len(problems)} item(s) {'missing' if a.check else 'need attention'}: {', '.join(problems)}."
              + ("  Run `python setup.py` to install them." if a.check
                 else "  Fix the lines marked " + BAD + " and run `python setup.py` again."))
        return 1
    print("\nAll set." + ("" if a.check else "  Make a video: see INSTALL.md > Make your first video."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
