"""Edit an episode: one-word captions over the frames, voice + music + SFX at -14 LUFS, H.264 encode,
plus a description file with the title and any credits.   (MILO_EP=epNN)  python engine/post.py OUT.mp4"""
import json, os, re, subprocess, sys
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont
from epdata import EP, WORK, MILO, load_words
import palette

W, H, SR, FPS = 1080, 1920, 48000, 30
FONT = os.path.join(MILO, "assets", "fonts", "Montserrat-ExtraBold.ttf")
RED, WHITE = (0xEC, 0x1C, 0x24, 255), (255, 255, 255, 255)
CAP_Y = 0.64 * H


def frame(t):
    return int(round(t * FPS))


def caption_layer(word, key):
    """Full-frame RGBA: 104 px Montserrat ExtraBold, 13 px black outline, 60% black shadow (+4, +7)."""
    size = 104
    font = ImageFont.truetype(FONT, size)
    while font.getbbox(word, stroke_width=13)[2] - font.getbbox(word, stroke_width=13)[0] > W - 60:
        size -= 2
        font = ImageFont.truetype(FONT, size)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((W / 2 + 4, CAP_Y + 7), word, font=font, anchor="mm",
                                fill=(0, 0, 0, 255), stroke_width=13, stroke_fill=(0, 0, 0, 255))
    a = np.array(shadow)
    a[..., 3] = (a[..., 3].astype(np.float32) * 0.6).astype(np.uint8)
    layer = Image.fromarray(a)
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(top).text((W / 2, CAP_Y), word, font=font, anchor="mm",
                             fill=RED if key else WHITE, stroke_width=13, stroke_fill=(0, 0, 0, 255))
    layer.alpha_composite(top)
    return layer


# ---- "real" look captions (from the reference study): 1-3 lowercase words, regular sans, white,
# thin black outline + soft shadow, centred at 60% height; key words alone in red CAPS; 2-frame pop.
REAL = os.environ.get("MILO_LOOK") in ("real", "brick")      # brick uses the real captions too
BRICK = os.environ.get("MILO_LOOK") == "brick"
SANS = next((f for f in (r"C:\Windows\Fonts\arial.ttf", "/Library/Fonts/Arial.ttf",
                         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf") if os.path.exists(f)), FONT)
RED_REAL = (0xE0, 0x10, 0x10, 255)


def chunk_words(words):
    """Group word indices into captions of 1-3 words; break on punctuation, line change, key words, 16 chars."""
    groups, cur = [], []
    for i, w in enumerate(words):
        prev = words[cur[-1]] if cur else None
        brk = cur and (len(cur) == 3 or w["key"] != prev["key"] or re.search(r"[.,!?…:;]$", prev["text"])
                       or prev.get("line") != w.get("line")
                       or len(" ".join(words[j]["text"] for j in cur + [i])) > 16)
        if brk:
            groups.append(cur)
            cur = []
        cur.append(i)
    if cur:
        groups.append(cur)
    return groups


def chunk_text(words, g):
    t = " ".join(re.sub(r"[.,…:;\"]+$", "", words[j]["text"]) for j in g)
    key = any(words[j]["key"] for j in g)
    return (t.upper() if key else t.lower().replace(" i ", " I ").replace("i'm", "I'm")), key


def caption_layer_real(text, key, pop=1.0):
    from PIL import ImageFilter
    size = int(104 * pop)
    font = ImageFont.truetype(SANS, size)
    while font.getbbox(text, stroke_width=6)[2] - font.getbbox(text, stroke_width=6)[0] > W - 80:
        size -= 2
        font = ImageFont.truetype(SANS, size)
    cy = 0.60 * H
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((W / 2 + 3, cy + 4), text, font=font, anchor="mm", fill=(0, 0, 0, 255),
                            stroke_width=8, stroke_fill=(0, 0, 0, 255))
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    a = np.array(sh)
    a[..., 3] = (a[..., 3].astype(np.float32) * 0.8).astype(np.uint8)
    layer = Image.fromarray(a)
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(top).text((W / 2, cy), text, font=font, anchor="mm", fill=RED_REAL if key else WHITE,
                             stroke_width=9 if key else 6, stroke_fill=(0, 0, 0, 255))
    layer.alpha_composite(top)
    return layer


def caption_track_real(words, nf):
    """Returns per-frame (chunk index, popped?) and the layers dict {(i, pop): image}."""
    groups = chunk_words(words)
    track, layers = [None] * nf, {}
    for gi, g in enumerate(groups):
        text, key = chunk_text(words, g)
        layers[(gi, 0)] = caption_layer_real(text, key)
        layers[(gi, 1)] = caption_layer_real(text, key, 1.12)
        a = frame(words[g[0]]["start"] - 0.03)
        b = frame(words[groups[gi + 1][0]]["start"] - 0.03) if gi + 1 < len(groups) else frame(words[g[-1]]["end"] + 0.25)
        for f in range(max(0, a), min(nf, b)):
            track[f] = (gi, 1 if f - a < 2 else 0)
    return track, layers


def caption_track(words, nf):
    track = [None] * nf
    for i, w in enumerate(words):
        a = frame(w["start"] - 0.03)
        b = frame(words[i + 1]["start"] - 0.03) if i + 1 < len(words) else frame(w["end"] + 0.25)
        for f in range(max(0, a), min(nf, b)):
            track[f] = i
    return track


def db(x):
    return 10 ** (x / 20)


def decode(path, max_s=None):
    """Any audio file -> 48 kHz stereo float32 via ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    y = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    return y


def trim_hit(y, max_s):
    """Start on the hit (first sample above -40 dBFS, minus 5 ms) and cap the length with a short fade."""
    lvl = np.abs(y).max(axis=1)
    idx = np.where(lvl > db(-40))[0]
    s = max(0, idx[0] - int(0.005 * SR)) if len(idx) else 0
    y = y[s:s + int(max_s * SR)]
    n = min(len(y), int(0.06 * SR))
    if len(y) >= int(max_s * SR) - 1 and n:
        y[-n:] *= np.linspace(1, 0, n)[:, None]
    return y


def lufs(y):
    tmp = os.path.join(WORK, "_lufs.wav")
    sf.write(tmp, y, SR, subtype="FLOAT")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", tmp, "-af", "ebur128=framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True)
    os.remove(tmp)
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])


def clack(seed, kind="step"):
    """A synthesized plastic clack (no sample needed): a sharp click plus two short hard-plastic resonances.
    'snap' = two clicks 11 ms apart, brighter, like a brick pressed onto studs."""
    rng = np.random.default_rng(seed)
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    click = np.diff(rng.standard_normal(n) * np.exp(-t / 0.0025), prepend=0.0)
    f = rng.uniform(2300, 3300) if kind == "step" else rng.uniform(3200, 4600)
    y = 0.6 * click + np.sin(2 * np.pi * f * t) * np.exp(-t / 0.010) \
        + 0.45 * np.sin(2 * np.pi * f * 1.57 * t + 1.0) * np.exp(-t / 0.006)
    if kind == "snap":
        k = int(0.011 * SR)
        y[k:] += 0.8 * y[:n - k]
    y = (y / np.abs(y).max()).astype(np.float32)
    return np.stack([y, y], axis=1)


def add_foley(out):
    """Brick look: a tiny clack on each footstep and brick snaps on each transformation, from
    work/<ep>/foley.json (written by the Blender build; times sit on the held stop-motion frames)."""
    pth = os.path.join(WORK, "foley.json")
    if not os.path.exists(pth):
        print("foley: no foley.json (build in the brick look first)")
        return
    fl = json.load(open(pth))
    n = len(out)
    for kind, level in (("steps", -24.0), ("snaps", -19.0)):
        for k, t0 in enumerate(fl.get(kind, [])):
            s = clack(1000 * (kind == "snaps") + k, "snap" if kind == "snaps" else "step") * db(level)
            i = int(round(t0 * SR))
            j = min(n, i + len(s))
            if 0 <= i < n:
                out[i:j] += s[:j - i]
    print(f"foley: {len(fl.get('steps', []))} steps, {len(fl.get('snaps', []))} snaps")


def mix(plan, dur):
    n = int(round(dur * SR))
    out = np.zeros((n, 2), np.float32)
    voice, sr = sf.read(os.path.join(WORK, "voice.wav"), dtype="float32", always_2d=True)
    voice = np.repeat(voice[:, :1], 2, axis=1)
    voice *= db(-15) / np.abs(voice).max()
    out[:min(n, len(voice))] += voice[:n]

    rel, credit = palette.MUSIC[plan["music"]]
    if not os.path.exists(palette.path(rel)):          # a missing music file just means no music bed
        print(f"music: {rel} not found, mixing without music")
        rel, credit = None, None
    music = decode(palette.path(rel)) if rel else np.zeros((n, 2), np.float32)
    music = music[int(2 * SR):] if len(music) > 20 * SR else music     # skip a slow intro
    while len(music) < n:
        music = np.concatenate([music, music])
    music = music[:n]
    loud = music[np.abs(music).max(axis=1) > 1e-4]
    rms = np.sqrt(np.mean(loud ** 2)) if len(loud) else 1.0
    music *= db(-27) / rms
    t = np.arange(n) / SR
    env = np.ones(n, np.float32)
    for a, b in plan["music_gaps"]:
        down = np.clip((a - t) / 0.3, 0, 1)
        up = np.clip((t - b) / 0.15, 0, 1) if b is not None else 0
        tb = b if b is not None else dur + 1
        env *= np.where(t < a, down, np.where(t < tb, 0.0, up))
    out += music * env[:, None]
    credits = {credit} if credit else set()

    cache = {}
    for t0, name, level in plan["sfx"]:
        rel, cr = palette.SFX[name]
        if not os.path.exists(palette.path(rel)):      # sound not installed: skip it, don't crash
            print(f"sfx: {name} ({rel}) not found, skipped")
            continue
        if cr:
            credits.add(cr)
        if name not in cache:
            s = trim_hit(decode(palette.path(rel)), 2.5 if name == "sting" else 1.5)
            cache[name] = s / max(1e-6, np.abs(s).max())
        s = cache[name] * db(level)
        i = int(round(t0 * SR))
        j = min(n, i + len(s))
        if i < n:
            out[i:j] += s[:j - i]

    if BRICK:
        add_foley(out)
    g = db(-14 - lufs(out))
    for _ in range(3):
        y = 0.89 * np.tanh(out * g / 0.89)
        err = -14 - lufs(y)
        if abs(err) < 0.1:
            break
        g *= db(err)
    print(f"mix: {lufs(y):.2f} LUFS, peak {20 * np.log10(np.abs(y).max()):.2f} dBFS")
    return y, sorted(credits)


def plan_credits(plan):
    out = {palette.MUSIC[plan["music"]][1]} | {palette.SFX[name][1] for _, name, _ in plan["sfx"]}
    return sorted(c for c in out if c)


def write_meta(dst, plan, credits):
    """outbox/<slug>.txt: title, description (with credits) and a pinned comment, ready to paste."""
    sys.path.insert(0, os.path.join(MILO, "episodes"))
    try:
        import youtube
        m = youtube.META[EP]
        text = ["TITLE", m["title"], "", "DESCRIPTION", youtube.description(EP, credits), "",
                "PINNED COMMENT", m["pinned"]]
    except (ImportError, KeyError):
        text = [plan["title"], "", "#stopmotion #brickanimation #animation #shorts", ""]
        text += ["Credits:"] + credits if credits else []
    with open(os.path.splitext(dst)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(text) + "\n")


def main():
    dst = os.path.abspath(sys.argv[1])
    plan = json.load(open(os.path.join(WORK, "plan.json"), encoding="utf-8"))
    if "--meta-only" in sys.argv:
        write_meta(dst, plan, plan_credits(plan))
        print("wrote", os.path.splitext(dst)[0] + ".txt")
        return
    words = load_words()
    nf = frame(plan["end"])
    wav = os.path.join(WORK, "mix.wav")
    y, credits = mix(plan, nf / FPS)
    sf.write(wav, y, SR, subtype="PCM_24")
    if REAL:
        track, layers = caption_track_real(words, nf)
    else:
        layers = {i: caption_layer(w["text"], w["key"]) for i, w in enumerate(words)}
        track = caption_track(words, nf)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-shortest", dst]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(nf):
        im = Image.open(os.path.join(WORK, "frames", f"f_{f:04d}.png")).convert("RGBA")
        if track[f] is not None:
            im.alpha_composite(layers[track[f]])
        p.stdin.write(im.convert("RGB").tobytes())
    p.stdin.close()
    p.wait()
    write_meta(dst, plan, credits)
    print("wrote", dst)


if __name__ == "__main__":
    main()
