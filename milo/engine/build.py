"""Blender entry: builds one episode from work/<ep>/plan.json + episodes/<ep>.py.
blender -b --factory-startup --python engine/build.py -- MODE OUT [args]   (env MILO_EP=epNN)
  stills OUT [names] : 50% still from the middle of every shot (12 samples)
  frames OUT [A B]   : PNG frames A..B (default all)
  blend OUT          : save the .blend"""
import importlib, json, math, os, random, sys
from math import radians, sin, cos

ENGINE = os.path.dirname(os.path.abspath(__file__))
MILO = os.path.dirname(ENGINE)
for p in (ENGINE, MILO, os.path.join(MILO, "episodes")):
    sys.path.insert(0, p)
from mathutils import Quaternion
import core
from core import (Char, POSES, LEAD, Vector, back, facing, frame, heading_to, keys, lin, puff, part, empty,
                  text, SC, CLOTH, SKINS, HAIRC, STYLES)
import sets as SETLIB
from dsl import parse_at, parse_event, word_time
from cast import CAST

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = ARGV[0] if ARGV else "blend"
OUT = os.path.abspath(ARGV[1]) if len(ARGV) > 1 else os.path.join(MILO, "work", "render")
EP = os.environ.get("MILO_EP", "ep01")
WORK = os.path.join(MILO, "work", EP)
PLAN = json.load(open(os.path.join(WORK, "plan.json"), encoding="utf-8"))
WORDS = json.load(open(os.path.join(WORK, "words.json")))["words"]
D = importlib.import_module(EP)
SHOTS = PLAN["shots"]
core.init(frame(PLAN["end"]))
NF = core.NF
LOOK = os.environ.get("MILO_LOOK", "brand")
BRICK = LOOK == "brick"
REALCAM = LOOK in ("real", "brick")        # the brick look shoots with the real look's camera grammar
if BRICK:
    import look as _look
    BRICK_CFG = _look.BRICK

POSES.update({            # the rest (point, phone, shrug, ...) live in core.POSES
    "peace": {"shp": -150, "spp": -42, "elp": -40, "shn": 10, "spn": 25, "szn": -20, "eln": -70, "twist": -8,
              "nod": -6, "lean": -3},
    "think": {"shp": -112, "spp": -20, "szp": 40, "elp": -95, "shn": -5, "spn": 3, "szn": 8, "eln": -16, "nod": 8,
              "turnh": -8},
    "sit": {"hipp": -88, "hipn": -88, "crouch": -0.95, "shp": -25, "shn": -25, "szp": 15, "szn": 15, "elp": -45,
            "eln": -45},
    "sleep": {"nod": 18, "lean": 6, "shp": -10, "shn": -10, "elp": -20, "eln": -20},
    "float": {"shp": -40, "shn": -40, "spp": 30, "spn": 30, "elp": -30, "eln": -30, "hipp": 15, "hipn": -15},
})

# ---------------------------------------------------------------- forms (transformation looks)
GREY = "#767676"
STONE = {"legs": ["pnt", "leg", "shoe", "sole"], "arms": ["pnt", "leg", "shoe", "sole", "arm", "hand", "slv", "cuff"],
         "chest": ["pnt", "leg", "shoe", "sole", "arm", "hand", "slv", "cuff", "torso", "acc"],
         "all": ["pnt", "leg", "shoe", "sole", "arm", "hand", "slv", "cuff", "torso", "acc", "head", "hair"]}
# "cuff" greys the jacket cuffs, "acc" every worn accessory / held prop (core.Char.write_outfits)


def form_outfit(own, form):
    o = dict(own)
    o["acc"] = list(own.get("acc", []))
    o["parts"] = dict(own.get("parts", {}))
    base, _, stage = form.partition("_")
    if base in ("stone", "statue"):
        for k in STONE[stage or "all"]:
            o["parts"][k] = GREY
    elif base == "ghost":
        o["alpha"] = 0.38
    elif base == "headless":             # head, hair and head gear gone (pop: the head flies off)
        o["headless"] = True
    elif base in ("rock", "paper", "scissors"):
        o["acc"] += [base]
    elif base == "pizza":
        n = int(stage or 4)
        o["acc"] += ["pep_arms"] + (["olives"] if n >= 3 else []) + (["pizza"] if n >= 4 else [])
        if n >= 2:
            o["parts"].update(arm="#F7D35C", slv="#F7D35C")
    elif base == "chicken":
        n = int(stage or 4)
        o["acc"] += ["feathers"] + (["beak"] if n >= 2 else []) + (["wings"] if n >= 3 else [])
        if n >= 4:
            o["parts"].update(torso="#FFFFFF", slv="#FFFFFF", arm="#FFFFFF", leg="#F39C12", shoe="#F39C12")
    elif base in ("hold", "wear"):       # carrying/stuck props or extra gear: hold_cookie+beanbag
        o["acc"] += stage.split("+")
    elif base == "look":                 # wear another cast member's clothes: look_brax
        other = CAST[stage]["own"]
        o.update({k: other[k] for k in ("shirt", "pants", "shoes", "sleeve") if k in other})
        o["acc"] = [a for a in other.get("acc", []) if a != "glasses"]
    else:
        raise KeyError(f"unknown form {form}")
    return o


def forms_used():
    used = {}
    for li, st in enumerate(D.STAGE):
        for e in map(parse_event, st["do"]):
            if e["act"] == "form":
                used.setdefault(e["who"], set()).add(e["args"][0])
            elif e["act"] == "pop":
                used.setdefault(e["who"], set()).add("headless")
    return used


# ---------------------------------------------------------------- props (accessories held or stuck)
def prop_acc(kind, ch, col=None):
    """Hand / body props from engine/props.py (phone, cash_l, backpack, ...); None for other accessories."""
    import props
    return props.build(kind, ch, col)


_orig_acc = core.acc_parts


def tape_acc(ch, col=None):
    """Two crossed strips of tape over the mouth, on the head itself (so a popped head keeps it)."""
    bb = [Vector(v) for v in ch.head.bound_box]
    x0, x1 = min(v.x for v in bb), max(v.x for v in bb)
    y0 = min(v.y for v in bb)
    z0, z1 = min(v.z for v in bb), max(v.z for v in bb)
    w, h = x1 - x0, z1 - z0
    zc = z0 + 0.3 * h
    return [part(ch.name + f"_tape{k}", "cube", ((x0 + x1) / 2, y0 + 0.02, zc), (0.62 * w, 0.06, 0.13 * h),
                 col or "#C9C9C9", ch.head, rot=(0, r, 0)) for k, r in enumerate((14, -14))]


def acc_parts(kind, col, ch):
    if kind == "tape":
        return tape_acc(ch, col)
    p = prop_acc(kind, ch, col)
    return p if p is not None else _orig_acc(kind, col, ch)


core.acc_parts = acc_parts


# ---------------------------------------------------------------- static set props
def build_props(S):
    for spec in getattr(D, "PROPS", []):
        kind, where = spec[0], spec[1]
        st, _, spot = where.partition(".")
        x, y, z, hd = S[st].at(spot)
        dx, dy = (spec[2], spec[3]) if len(spec) > 3 else (0, 0)
        x, y = x + dx, y + dy
        z = z + (spec[4] if len(spec) > 4 else 0)          # optional 5th: raise it (a fan under the ceiling)
        nm = f"prop_{kind}_{x:.0f}_{y:.0f}"
        if kind.startswith("sign:"):
            part(nm, "cube", (x, y, z + 3.2), (5.2, 0.2, 1.8), "#FFFFFF")
            part(nm + "p", "cube", (x, y + 0.1, z + 1.2), (0.25, 0.2, 2.4), "#8B5A2B")
            text(nm + "t", kind[5:], (x, y - 0.13, z + 3.2), 0.75, "#EC1C24")
        elif kind == "pizzabox":
            part(nm, "cube", (x, y, z + 2.75), (3.4, 3.4, 0.25), "#F2E6D0")
            part(nm + "s", "prism", (x, y - 0.4, z + 2.9), (0.1, 1.4, 1.5), "#F4B942", rot=(90, 0, 0))
        elif kind == "cake":
            part(nm, "cyl", (x, y, z + 3.0), (2.4, 2.4, 1.2), "#FF9EC7")
            part(nm + "c", "cyl", (x, y, z + 3.9), (0.15, 0.15, 0.6), "#FFD21F")
        elif kind == "speaker":
            part(nm, "cube", (x, y, z + 1.6), (1.6, 1.4, 3.2), "#1A1A1A")
            part(nm + "c", "cyl", (x, y - 0.72, z + 2.2), (1.0, 1.0, 0.1), "#555555", rot=(90, 0, 0))
        elif kind == "trampoline":
            part(nm, "cyl", (x, y, z + 1.0), (5.0, 5.0, 0.2), "#1A1A1A")
            part(nm + "r", "cyl", (x, y, z + 0.95), (5.4, 5.4, 0.15), "#2D5BFF")
        elif kind == "ladder":
            for dxx in (-0.7, 0.7):
                part(nm + f"s{dxx}", "cube", (x + dxx, y, z + 4), (0.2, 0.2, 8), "#C98B4A")
            for k in range(7):
                part(nm + f"r{k}", "cube", (x, y, z + 1 + k), (1.4, 0.15, 0.15), "#C98B4A")
        elif kind == "car":
            part(nm, "cube", (x, y, z + 1.6), (7, 3.4, 2), "#E5262B")
            part(nm + "t", "cube", (x - 0.4, y, z + 3.1), (4, 3.2, 1.4), "#9FE3FF")
            for wx in (-2.3, 2.3):
                for wy in (-1.6, 1.6):
                    part(nm + f"w{wx}{wy}", "cyl", (x + wx, y + wy, z + 0.7), (1.4, 1.4, 0.5), "#1A1A1A", rot=(90, 0, 0))
        elif kind in ("dog", "cat"):
            pet(nm, kind, (x, y, z), hd)
        elif kind == "tv":            # a flat TV on a low stand, the screen glowing
            part(nm + "s", "cube", (x, y, z + 0.9), (5.0, 1.6, 1.8), "#5A3A1A")
            part(nm, "cube", (x, y, z + 3.9), (6.2, 0.35, 3.6), "#1A1A1A")
            glow = core.material("TVGlow", color="#4FC3FF", emission=1.2)
            for k, sy in enumerate((-0.19, 0.19)):        # lit on both faces: it reads from either side
                part(nm + f"g{k}", "cube", (x, y + sy, z + 3.9), (5.6, 0.05, 3.1), "#4FC3FF", mat=glow)
        elif kind == "fan":           # ceiling fan: rod, hub and four blades (z = the hub; 5th PROPS value)
            part(nm + "r", "cyl", (x, y, z + 0.8), (0.18, 0.18, 1.6), "#3A3F47")
            part(nm, "cyl", (x, y, z), (0.9, 0.9, 0.45), "#3A3F47")
            for k in range(4):
                a = radians(45 + 90 * k)
                part(nm + f"b{k}", "cube", (x + 2.1 * math.cos(a), y + 2.1 * math.sin(a), z - 0.05),
                     (3.4, 0.9, 0.08), "#C98B4A", rot=(0, 0, 45 + 90 * k))
        elif kind == "alarm":         # wall fire alarm: red box + a strobe that blinks all film long
            part(nm, "cube", (x, y, z + 6.0), (1.1, 0.4, 1.1), "#E5262B")
            b = part(nm + "l", "sphere", (x, y - 0.3, z + 6.0), (0.55, 0.4, 0.55), "#FFFFFF",
                     mat=core.material("Strobe", color="#FFF6C8", emission=6.0), shadow=False)
            core.step_keys(b, "hide_render", -1, [(f, float((f // 8) % 2)) for f in range(0, NF, 8)])
        else:
            raise KeyError(kind)


def pet(nm, kind, pos, hd):
    col = "#C68642" if kind == "dog" else "#F39C12"
    root = empty(nm, pos)
    root.rotation_euler.z = radians(hd)
    part(nm + "b", "cube", (0, 0, 0.9), (1.8, 0.8, 0.8), col, root)
    for i, (x, y) in enumerate(((-0.65, -0.25), (-0.65, 0.25), (0.65, -0.25), (0.65, 0.25))):
        part(nm + f"l{i}", "cube", (x, y, 0.3), (0.26, 0.26, 0.6), col, root)
    head = empty(nm + "h", (-0.95, -0.05, 1.4), root)
    part(nm + "hd", "cube", (0, 0, 0), (0.95, 0.85, 0.85), col, head)
    for x in (-0.27, 0.27):
        if kind == "cat":
            part(nm + f"e{x}", "cone", (x, 0, 0.6), (0.34, 0.22, 0.45), col, head)
        else:
            part(nm + f"e{x}", "cube", (x * 1.6, 0.05, 0.1), (0.2, 0.4, 0.7), "#8B5A2B", head)
        part(nm + f"ey{x}", "cube", (x * 0.75, -0.44, 0.1), (0.14, 0.05, 0.22), "#111111", head)
    part(nm + "n", "cube", (0, -0.44, -0.12), (0.16, 0.05, 0.1), "#111111", head)
    tail = empty(nm + "t", (0.9, 0, 1.2), root)
    part(nm + "tm", "cyl", (0, 0, 0.5), (0.2, 0.2, 1.1), col, tail)
    frames = list(range(NF))
    keys(tail, "rotation_euler", 1, frames, [radians(30 * sin(2 * math.pi * 2.2 * f / 30) - 25) for f in frames])
    keys(head, "rotation_euler", 2, frames, [radians(12 * sin(2 * math.pi * 0.6 * f / 30)) for f in frames])


# ---------------------------------------------------------------- cast, crowd, staging
def make_cast(S):
    used = forms_used()
    C = {}
    CAST.update(getattr(D, "EXTRAS", {}))       # one-off characters for this episode
    for key in D.WHO:
        c = CAST[key]
        outfits = {"own": dict(c["own"])}
        for f in used.get(key, set()) - {"own"}:
            outfits[f] = form_outfit(c["own"], f)
        C[key] = Char(key, (0, 0, -1000), 0, c["skin"], c["hair"], c["hair_col"], outfits, "own",
                      c.get("face", "smile"), scale=c.get("scale", 1.0))
    C["_crowd"] = make_crowd(S)
    return C


CROWD_STYLES = STYLES + ["swoop", "pigtails", "spiky", "short"]
CROWD_ACC = ["glasses", "cap", "cap_back", "headphones", "bow", "chain"]


def _weighted(rnd, items):
    r = rnd.uniform(0, sum(w for _, w in items))
    for v, w in items:
        r -= w
        if r <= 0:
            return v
    return items[-1][0]


def make_crowd(S):
    """D.CROWD = (set, form, count, scale). Every member gets its own pose (statues: frozen mid-joke, some with a
    stone mic), face, head turn (+-25 deg), body yaw (+-20), scale (0.92-1.06), hair, shirt print and maybe an
    accessory, a small position jitter that never brings two closer than ~2.2 units, and its own breathing/bob
    rhythm. All seeded, so every render of an episode matches."""
    if not getattr(D, "CROWD", None):
        return []
    import look
    st, form, n = D.CROWD[:3]
    cscale = D.CROWD[3] if len(D.CROWD) > 3 else 1.0
    spots = S[st].crowd
    step = max(1, len(spots) / n)
    rnd = random.Random(11)
    stone = bool(form) and form.partition("_")[0] in ("stone", "statue")
    gap = 2.2 * max(1.0, cscale)
    picked = [spots[int(i * step)] for i in range(min(n, len(spots)))]
    extra = forms_used().get("crowd", set()) - {"own", form}    # staged crowd forms (crowd pop -> headless)
    placed, crowd = [], []                # placed: (spot xyz, jittered xyz)
    for i, (x, y, z, hd) in enumerate(picked):
        acc = [rnd.choice(CROWD_ACC)] if not stone and rnd.random() < 0.35 else []
        own = dict(shirt=rnd.choice(CLOTH), pants=rnd.choice(CLOTH), shoes=rnd.choice(["#2B2B2B", "#FFFFFF"]),
                   sleeve=rnd.choice(["short", "long"]), plen="long", acc=acc)
        pose = _weighted(rnd, core.STATUE_POSES if stone else core.CROWD_POSES)
        outfits = {"own": own}
        for f in extra:
            outfits[f] = form_outfit(own, f)
        if form:
            outfits[form] = form_outfit(own, form)
            if stone and pose == "mic":           # a comedian frozen mid-joke, stone mic and all
                outfits[form]["acc"].append("mic:#8E8E8E")
        raised = z > 0.05                         # on a pedestal / bleacher step: stay on it
        jx, jy = (0.25, 0.15) if raised else (0.45, 0.45)
        p0, pos = Vector((x, y, z)), Vector((x, y, z))
        for _ in range(12):
            q = Vector((x + rnd.uniform(-jx, jx), y + rnd.uniform(-jy, jy), z))
            if all((q - b).length >= min(gap, (p0 - a).length) - 1e-6 for a, b in placed):
                pos = q
                break
        placed.append((p0, pos))
        face = rnd.choice(core.STATUE_FACES if stone else core.CROWD_FACES)
        ch = Char(f"crowd{i}", tuple(pos), hd + rnd.uniform(-20, 20), rnd.choice(SKINS), rnd.choice(CROWD_STYLES),
                  rnd.choice(HAIRC), outfits, form or "own", face, scale=cscale * rnd.uniform(0.92, 1.06),
                  crowd=True)
        ch.set = st
        ch.poses = [(-10.0, pose)]
        ch.jbias = {"turnh": rnd.uniform(-25, 25)}
        ra = random.Random(500 + i)               # own stream: the layout above stays as it was
        ch.jbias.update(roll=ra.uniform(-8, 8), tilt=ra.uniform(-2.5, 2.5))   # weight on one side, head tilted
        ch.idle_hz, ch.bob_hz, ch.phase = rnd.uniform(0.5, 0.95), rnd.uniform(1.3, 1.9), rnd.uniform(0, 10)
        ch.variants = random.Random(1000 + i)
        if stone:
            ch.freeze = {form}
            ch.bob_windows = []
        else:
            ch.bob_windows = [(0, PLAN["end"])] if rnd.random() < 0.7 else []
        look.PRINT_OF[ch.name] = 0 if stone else rnd.randrange(8)
        crowd.append(ch)
    return crowd


def line_start(li):
    return next(s["t0"] for s in SHOTS if s["line"] == li)


def chars_in(C, st, t):
    out = [c for k, c in C.items() if k != "_crowd" and getattr(c, "set_at", lambda t: None)(t) == st]
    return out + [c for c in C["_crowd"] if c.set == st]


def stage(C, S):
    where = {}                 # who -> [(t, set)]
    for li, st in enumerate(D.STAGE):
        t0 = max(0.0, line_start(li) - 0.06)
        for a in st["at"]:
            who, s, spot, face, hd = parse_at(a)
            x, y, z, shd = S[s].at(spot)
            where.setdefault(who, []).append((t0, s, Vector((x, y, z)), hd if hd is not None else shd, face))
    for who, items in where.items():
        ch = C[who]
        for t0, s, pos, hd, face in items:
            if face:
                other = [it for it in where.get(face, []) if it[0] <= t0 + 1e-6]
                if other:
                    hd = heading_to(other[-1][2] - pos)
            ch.place(t0, pos, hd)
        ch.set_at = (lambda its: lambda t: ([s for t0, s, *_ in its if t0 <= t] or [None])[-1])(items)
    for k, c in C.items():
        if k != "_crowd" and not hasattr(c, "set_at"):
            c.set_at = lambda t: None

    for li, st in enumerate(D.STAGE):
        for e in map(parse_event, st["do"]):
            t = word_time(WORDS, li, e["word"], e["nth"], e["off"])
            who = e["who"]
            if who == "crowd":
                targets = C["_crowd"]
            elif who == "all":
                targets = chars_in(C, st["set"], t)
            else:
                targets = [C[who]]
            for ch in targets:
                apply(C, S, ch, e, t, st)
    # Milo's signature pose on his "Me? I'm the ___" word
    for li, b in enumerate(PLAN_BEATS):
        if b == "ME" and "milo" in C:
            kw = [w for w in WORDS if w["line"] == li and w["key"]]
            if kw:
                C["milo"].at(kw[-1]["start"], "peace", "wink")


def chest(ch, t):
    p, _, _ = ch.base(t)
    return p + Vector((0, 0, ch.lift_at(t) + 3.4 * ch.scale * ch.size_at(t)))


def apply(C, S, ch, e, t, st):
    a, args = e["act"], e["args"]
    if a == "pose":
        p, _, f = args[0].partition("/")
        ch.at(t, p or None, f or None)
    elif a == "face":
        ch.at(t, None, args[0])
    elif a == "form":
        ch.wear(t, args[0])
        if "nopuff" not in args:
            puff(t, chest(ch, t), 1.5 * ch.scale * max(1.0, ch.size_at(t)) ** 0.5)
    elif a == "puff":
        puff(t, chest(ch, t), float(args[0]) if args else 1.5)
    elif a == "size":
        ch.resize(t, float(args[0]), float(args[1]) if len(args) > 1 else 0.3)
    elif a == "lift":
        ch.lift(t, float(args[0]), float(args[1]) if len(args) > 1 else 0.5)
    elif a == "run":
        s, _, spot = args[0].partition(".")
        x, y, z, _ = S[s].at(spot)
        p, _, _ = ch.base(t)
        dur = max(0.6, min(1.6, (Vector((x, y, p.z)) - p).length / 8))
        ch.run(t, t + dur, (x, y), args[1] if len(args) > 1 else "run")
    elif a == "turn":
        ch.turn_to(t, C[args[0]].base(t)[0])
    elif a == "show":
        s, _, spot = args[0].partition(".")
        x, y, z, hd = S[s].at(spot)
        ch.place(t + 0.05, (x, y, z), float(args[1]) if len(args) > 1 else hd)
        ch.set_at = (lambda old, s_, t_: lambda tt: s_ if tt >= t_ else old(tt))(ch.set_at, s, t)
        puff(t, (x, y, z + 3.4 * ch.scale), 1.8)
    elif a == "hide":
        p, hd, _ = ch.base(t)
        ch.place(t + 0.05, (p.x, p.y, -1000), hd)
    elif a == "spin":
        ch.spin(t - 0.05, t + 0.45, 1)
    elif a == "flail":
        ch.flail(t, t + float(args[0]) if args else t + 1.0)
    elif a == "swap":
        o = C[args[0]]
        pa, ha, _ = ch.base(t)
        pb, hb, _ = o.base(t)
        ch.place(t, pb, hb)
        o.place(t, pa, ha)
        puff(t, chest(ch, t), 1.5)
    elif a == "snapto":
        target = C[args[0]].base(t)[0]
        pose, _, face = (args[1] if len(args) > 1 else "shock/shock").partition("/")
        cast = [c for c in chars_in(C, st["set"], t) if c is not C[args[0]]]
        cast.sort(key=lambda c: (c.base(t)[0] - target).length)
        for n, c in enumerate(cast):
            c.turn_to(t + 0.012 * n, target)
            c.at(t + 0.012 * n, pose or None, face or None)
    elif a == "pop":
        pop(C, S, ch, t, args)
    elif a == "pile":
        pile(C, S, ch, t, args)
    elif a == "sfx":
        pass
    else:
        raise KeyError(f"unknown action {a}")


# ---------------------------------------------------------------- popping heads (form headless + flying copies)
FLY = []        # dict(ch, t, p0, stops, hd, face, land, acc): a head copy that flies from the neck through stops
PILES = []      # dict(t, base, hd, chars, face): heads stacked on a spot
CROWD_FLY = 8   # at most this many crowd heads really fly (the rest vanish in their puff: render cost)


def _num(a):
    try:
        float(a)
        return True
    except ValueError:
        return False


def _stops(S, args):
    """['cafeteria.spot1', '0', '3', '3.4', 'grin'] -> ([(Vector, spot heading)], other words).
    A stop is set.spot plus optional dx dy dz (dz = the surface height the head lands on)."""
    stops, words = [], []
    for a in args:
        if "." in a and not _num(a):
            stops.append([a, []])
        elif _num(a) and stops:
            stops[-1][1].append(float(a))
        else:
            words.append(a)
    out = []
    for ref, d in stops:
        st, _, spot = ref.partition(".")
        x, y, z, hd = S[st].at(spot)
        d = d + [0.0] * 3
        out.append((Vector((x + d[0], y + d[1], z + d[2])), hd))
    return out, words


def pop(C, S, ch, t, args):
    """'Pop> dad pop home.couch 0 -1 2.4': the head (hair, head gear, current face) pops off in a puff and flies
    on an arc to that spot, through every listed stop ('pop cafeteria.spot1 0 6 8.6 cafeteria.spot1 2 -2' hits a
    fan, then lands on the floor), bounces once and stays. 'pop up' flies up out of the shot; 'pop scatter' (and a
    crowd pop with no stop) lands on the floor nearby. The body keeps acting headless (form headless). A face name
    sets the flying head's face."""
    if ch.crowd:
        t += 0.03 * (int(ch.name[5:]) % 5)          # a ripple, not one beat
    _, hd, _ = ch.base(t)
    acc = ch.outfits[max((w for w in ch.wears if w[0] <= t), key=lambda w: w[0])[1]].get("acc", [])
    ch.wear(t, "headless")
    p0 = ch.head_pos(t)
    puff(t, p0, 1.2 * ch.scale * ch.size_at(t))
    stops, words = _stops(S, args)
    face = next((w for w in words if w in core.FACE_IDS), None) or ch.face_at(t)
    if ch.crowd and sum(1 for f in FLY if f["ch"].crowd) >= CROWD_FLY:
        return
    rnd = random.Random(f"{ch.name}{t:.3f}")
    if "scatter" in words or (not stops and ch.crowd and "up" not in words):
        a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(2.5, 5.5)
        base = ch.base(t)[0]
        stops = [(Vector((base.x + r * cos(a), base.y + r * sin(a), base.z)), hd + rnd.uniform(-40, 40))]
    land = bool(stops)
    if not stops:                                    # up and away
        stops = [(p0 + Vector((rnd.uniform(-3, 3), rnd.uniform(-1, 1), 30)), hd)]
    FLY.append(dict(ch=ch, t=t, p0=p0, stops=stops, hd=hd, face=face, land=land, acc=list(acc), seed=rnd.random()))


def pile(C, S, ch, t, args):
    """'^> milo pile cafeteria.spot1 0 2 kai yumi brax grin': the heads of milo + the listed cast stacked in a pile
    on that spot (optional dx dy dz; a face for all of them, default grin), appearing with a puff. Flying heads
    of those characters (and of the crowd) that landed before it are cleared away when it appears."""
    stops, words = _stops(S, args)
    chars = [ch] + [C[w] for w in words if w in C]
    face = next((w for w in words if w in core.FACE_IDS), "grin")
    base, hd = stops[0]
    PILES.append(dict(t=t, base=base, hd=hd, chars=chars, face=face))
    puff(t, base + Vector((0, 0, 1.6)), 2.4)


def _head_kit(ch, acc):
    """[(object, matrix in head space)]: the head, its hair and the gear worn on the head."""
    from mathutils import Matrix
    hinv = ch.head.matrix_basis.inverted()

    def in_neck(ob):
        m, p = ob.matrix_basis.copy(), ob.parent
        while p is not None and p != ch.neck:
            m, p = p.matrix_basis @ m, p.parent
        return m if p == ch.neck else None
    out = [(ch.head, Matrix.Identity(4))]
    for ob in list(ch.hair) + [o for a in acc for o in ch.acc.get(a, [])]:
        m = in_neck(ob)
        if m is not None and ob != ch.head:
            out.append((ob, hinv @ m))
    return out


def _head_r(ch):
    zs = [v[2] for v in ch.head.bound_box]
    return (max(zs) - min(zs)) / 2 * ch.head.scale[2] * ch.scale


def _spawn(ch, kit, face, nm):
    root = empty(nm, (0, 0, -1000))
    obs = []
    for ob, m in kit:
        cp = ob.copy()
        cp.animation_data_clear()
        core.COLL.objects.link(cp)
        cp.parent = root
        cp.matrix_parent_inverse.identity()
        cp.matrix_basis = m
        cp.hide_render = False
        obs.append(cp)
    obs[0]["face"] = float(core.FACE_IDS[face])
    root.scale = (ch.scale,) * 3
    return root, obs


def _show_between(obs, f0, f1=None):
    seq = [(0, 1.0), (max(0, f0), 0.0)] + ([(f1, 1.0)] if f1 is not None else [])
    for ob in obs:
        core.step_keys(ob, "hide_render", -1, seq)


def build_heads():
    """Flying head copies (keyed every frame: the brick pass holds them on twos like everything else) and piles."""
    for n, fl in enumerate(FLY):
        ch = fl["ch"]
        root, obs = _spawn(ch, _head_kit(ch, fl["acc"]), fl["face"], f"pophead{n}")
        r = _head_r(ch)
        rnd = random.Random(fl["seed"])
        pts = [fl["p0"]] + [p + Vector((0, 0, r if fl["land"] else 0)) for p, _ in fl["stops"]]
        hds = [fl["hd"]] + [h for _, h in fl["stops"]]
        segs, tt = [], fl["t"]
        for a, b in zip(pts, pts[1:]):
            d = (b - a).length
            dur = 0.9 if not fl["land"] else min(0.85, max(0.4, 0.3 + d / 28))
            segs.append((tt, tt + dur, a, b, 0 if not fl["land"] else 1.2 + 0.18 * d + 0.3 * max(0, b.z - a.z)))
            tt += dur
        hop = 0.3 if fl["land"] else 0.0
        nxt = [p["t"] for p in PILES if p["t"] > fl["t"] and (ch in p["chars"] or ch.crowd)]
        gone = frame(tt) + 1 if not fl["land"] else (frame(min(nxt)) if nxt else None)
        f0, f1 = frame(fl["t"]), min(NF - 1, frame(tt + hop) + 1)
        frames = list(range(max(0, f0 - 1), f1 + 1))
        spin = rnd.choice((-1, 1))
        V = {k: [] for k in ("x", "y", "z", "rx", "ry", "rz")}
        for f in frames:
            t = f / core.FPS
            k = next((i for i, s_ in enumerate(segs) if t < s_[1]), None)
            if k is None:                                  # landed: one small hop, then rest
                u = min(1.0, max(0.0, (t - tt) / hop)) if hop else 1.0
                p = pts[-1] + Vector((0, 0, 4 * 0.18 * segs[-1][4] * u * (1 - u)))
                rx, ry, rz = 0.0, radians(10) * sin(u * math.pi) * spin, radians(hds[-1])
            else:
                a0, a1, pa, pb, h = segs[k]
                u = min(1.0, max(0.0, (t - a0) / (a1 - a0)))
                p = pa.lerp(pb, u) + Vector((0, 0, 4 * h * u * (1 - u)))
                rx = 2 * math.pi * spin * (k + core.smooth(u))
                ry = radians(25) * sin(2 * math.pi * u)
                rz = radians(hds[k] + (hds[k + 1] - hds[k]) * u)
            for key, v in zip(("x", "y", "z", "rx", "ry", "rz"), (p.x, p.y, p.z, rx, ry, rz)):
                V[key].append(v)
        for i, key in enumerate(("x", "y", "z")):
            keys(root, "location", i, frames, V[key])
        for i, key in enumerate(("rx", "ry", "rz")):
            keys(root, "rotation_euler", i, frames, V[key])
        _show_between(obs, f0, gone)
    for n, pl in enumerate(PILES):
        rnd = random.Random(31 + n)
        chars, k = pl["chars"], 0
        dd = 2 * max(_head_r(c) for c in chars)
        b = 1
        while b * (b + 1) // 2 < len(chars):
            b += 1
        rows, left = [], len(chars)
        for cnt in range(b, 0, -1):
            rows.append(min(cnt, left))
            left -= rows[-1]
            if left <= 0:
                break
        rot = Quaternion((0, 0, 1), radians(pl["hd"]))
        for row, cnt in enumerate(rows):
            for j in range(cnt):
                ch = chars[k]
                k += 1
                off = rot @ Vector(((j - (cnt - 1) / 2) * dd * 1.02, row * 0.18 * dd, 0))
                root, obs = _spawn(ch, _head_kit(ch, ch.outfits["own"].get("acc", [])), pl["face"],
                                   f"pilehead{n}_{k}")
                root.location = pl["base"] + off + Vector((0, 0, row * dd * 0.82 + _head_r(ch)))
                root.rotation_euler = (radians(rnd.uniform(-10, 10)), radians(rnd.uniform(-12, 12)),
                                       radians(pl["hd"] + rnd.uniform(-18, 18)))
                _show_between(obs, frame(pl["t"]))


# ---------------------------------------------------------------- cameras
def spec(pos, tgt, fov, push=0.0, slide=(0, 0, 0), end=0.85, follow=None):
    return dict(pos=Vector(pos), tgt=Vector(tgt), fov=fov, push=push, slide=Vector(slide), end=end, follow=follow,
                t_ref=None, roll=0.0, punch=1.0, subj=[])


def _h(s):
    """Stable per-shot hash (Python's str hash is salted per run)."""
    import zlib
    return zlib.crc32(s.encode("utf-8"))


def cam_for(shot, i, C, S):
    """Spec of one shot. insert:<who>[:face], pov:<who>, top:<who> and ots:<a>,<b> get a placeholder here (a
    close / a two-shot) plus sp["post"]; post_cams() places them on the posed, animated scene (hands and heads
    are only known then)."""
    preset, who = shot["cam"], shot["who"]
    if preset == "insert":
        nm, _, mod = who.partition(":")
        sp = cam_for(dict(shot, cam="close", who=nm), i, C, S)
        sp.update(preset="insert", post=("face" if mod == "face" else "prop", nm))
        return sp
    if preset == "fg":                 # a medium with foreground framing (real look: fg_frame); brand: a medium
        sp = _cam_for(dict(shot, cam="med"), i, C, S)
        sp.update(preset="med", want_fg=True)
        return sp
    if preset in ("pov", "top"):
        sp = cam_for(dict(shot, cam="close", who=who), i, C, S)
        sp.update(preset=preset, post=(preset, who))
        return sp
    if preset == "ots":
        a, b = who.split(",")
        sp = cam_for(dict(shot, cam="two", who=f"{a},{b}"), i, C, S)
        sp.update(preset="ots", post=("ots", a, b), side=(1, -1)[(i + _h(shot["name"])) % 2])
        return sp
    sp = _cam_for(shot, i, C, S)
    sp.setdefault("preset", preset)
    return sp


def _cam_for(shot, i, C, S):
    t = (shot["t0"] + shot["t1"]) / 2      # mid-shot, so characters who appear on a word are framed
    preset, who = shot["cam"], shot["who"]
    st = S[shot["set"]]
    if REALCAM:     # 3/4 angles, alternating sides, 22-34 deg off the face
        a = 22 + _h(shot["name"]) % 13
        side = (a, -a)[i % 2]
    else:
        side = (9, -9)[i % 2]
    if preset == "slide":
        p, g, fov, sv = st.slide
        return spec(p, g, fov, 0.0, sv, end=1.0)
    if preset == "wide" and (who in (None, "set") or who not in C):
        p, g, fov = st.wide
        return spec(p, g, fov, 1.2)
    if preset.startswith("two"):
        a, b = (C[x] for x in who.split(","))
        pa, pb = a.base(t)[0], b.base(t)[0]
        mid = (pa + pb) / 2
        d = pb - pa
        f = Vector((-d.y, d.x, 0)).normalized() if d.length > 0.1 else Vector((0, -1, 0))
        if f.y > 0:                # stay on the default camera side (-Y)
            f = -f
        f = (f + Vector((0, -0.6, 0))).normalized()
        dist = max(9.0, (d.length + 3.5) * 1.7)       # both fit across the 9:16 frame
        z = 3.0 * max(a.scale * a.size_at(t), b.scale * b.size_at(t))
        return spec(mid + f * dist + Vector((0, 0, z + 1.2)), mid + Vector((0, 0, z)), 54, 0.8, follow=a)
    ch = C[who]
    k = ch.scale * ch.size_at(t)
    hd = ch.base(t)[1]
    head = ch.head_pos(t)
    feet = head - Vector((0, 0, 4.66 * k))
    if preset != "close":
        # frame for a normal-size person (or the giant), so shrink and grow read against the world
        k = ch.scale * max(1.0, ch.size_at(t))
    if preset == "close":
        f = facing(hd + side)
        return spec(head + f * 6.4 * k + Vector((0, 0, -0.3 * k)), head + Vector((0, 0, -0.8 * k)), 40, 0.6 * k,
                    follow=ch)
    if preset == "med":
        f = facing(hd + side)
        return spec(feet + f * 10.5 * k + Vector((0, 0, 3.6 * k)), feet + Vector((0, 0, 2.9 * k)), 50, 0.8 * k,
                    follow=ch)
    if preset == "wide":
        f = facing(hd + side * 0.5)
        return spec(feet + f * 20 * k + Vector((0, 0, 6.5 * k)), feet + Vector((0, 0, 3.4 * k)), 62, 1.2 * k,
                    follow=ch)
    if preset == "low":
        f = facing(hd + side)
        return spec(feet + f * 11 * k + Vector((0, 0, 1.0)), head - Vector((0, 0, 0.6 * k)), 58, 0.8, follow=ch)
    if preset == "high":
        f = facing(hd + side)
        tg = feet + Vector((0, 0, 2.6 * k))      # ~38 deg down: face still readable, the whole body below it
        return spec(tg + f * 9.5 * k + Vector((0, 0, 7.4 * k)), tg, 54, 0.5 * k, follow=ch)
    raise KeyError(preset)


# ---------------------------------------------------------------- inserts + over-the-shoulder (placed on the posed scene)
def held_props(ch, t):
    """Hand props (acc strings, e.g. 'mic', 'cash_l', 'book:#2D5BFF') ch holds at time t."""
    import props
    name = max((w for w in ch.wears if w[0] <= t), key=lambda w: w[0], default=(0, "own"))[1]
    out = []
    for a in ch.outfits.get(name, {}).get("acc", []):
        kind = a.partition(":")[0]
        kind = kind[:-2] if kind.endswith("_l") else kind
        if kind in props.HAND_PROPS:
            out.append(a)
    return out


def _wm(ob, dg):
    return ob.evaluated_get(dg).matrix_world


def _head_now(ch, dg):
    return _wm(ch.head, dg).translation.copy()


def _head_box(ch, dg, head, k):
    """World bounding box (lo, hi) of ch's head + visible hair."""
    pts = []
    for o in [ch.head] + list(getattr(ch, "hair", None) or []):
        if o is None or o.type != "MESH" or _hidden(o):
            continue
        mw = _wm(o, dg)
        pts += [mw @ Vector(c) for c in o.bound_box]
    if not pts:
        return head - Vector((0.7 * k, 0.7 * k, 0.65 * k)), head + Vector((0.7 * k, 0.7 * k, 1.7 * k))
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def _proj(pos, q, th, p):
    """Screen position (x, y in -1..1, 9:16 frame) of world point p for a camera at pos / quat q, or None."""
    d = p - pos
    z = d.dot(q @ Vector((0, 0, -1)))
    if z <= 0.05:
        return None
    return d.dot(q @ Vector((1, 0, 0))) / (z * th * 9 / 16), d.dot(q @ Vector((0, 1, 0))) / (z * th)


def _text_slice(dg, pos, q, th, box, skip):
    """How badly the subject's head box slices background text (signs, boards): for every text object in
    frame, the share of it the head covers when that share is partial, plus a little for text cut by the frame
    edge. 0 = every text is clear (or fully out of frame)."""
    corners = [Vector((x, y, z)) for x in (box[0].x, box[1].x) for y in (box[0].y, box[1].y)
               for z in (box[0].z, box[1].z)]
    hp = [_proj(pos, q, th, p) for p in corners]
    if any(p is None for p in hp):
        return 0.0
    hx0, hx1 = min(p[0] for p in hp), max(p[0] for p in hp)
    hy0, hy1 = min(p[1] for p in hp), max(p[1] for p in hp)
    fwd = q @ Vector((0, 0, -1))
    hdep = ((box[0] + box[1]) / 2 - pos).dot(fwd)
    bad = 0.0
    for o in SC.objects:
        if o.type != "FONT" or _hidden(o) or o.name in skip:
            continue
        mw = _wm(o, dg)
        cs = [mw @ Vector(c) for c in o.bound_box]
        ctr = sum(cs, Vector()) / 8
        if (ctr - pos).dot(fwd) < hdep + 0.5:
            continue
        tp = [_proj(pos, q, th, p) for p in cs]
        if any(p is None for p in tp):
            continue
        tx0, tx1 = min(p[0] for p in tp), max(p[0] for p in tp)
        ty0, ty1 = min(p[1] for p in tp), max(p[1] for p in tp)
        if tx1 < -1 or tx0 > 1 or ty1 < -1 or ty0 > 1:
            continue
        if _first_hit(dg, pos, ctr, set(skip) | {o.name}, 0.97):
            continue                                   # behind a wall
        full = max(1e-6, (tx1 - tx0) * (ty1 - ty0))
        vis = (min(tx1, 1) - max(tx0, -1)) * (min(ty1, 1) - max(ty0, -1))
        cov = max(0.0, min(hx1, tx1, 1) - max(hx0, tx0, -1)) * max(0.0, min(hy1, ty1, 1) - max(hy0, ty0, -1))
        f = cov / max(1e-6, vis)
        if 0.02 < f < 0.97:
            bad += 0.4 + f
        cut = 1 - vis / full
        if 0.05 < cut < 0.95:
            bad += 0.3 * min(cut, 1 - cut) * 2
    return bad


def insert_cam_brand(sp, ch, mode, t, dg, k_i):
    """Brand look: macro on the prop in ch's hand (or an extreme close-up of the face): ~50 deg lens, slightly
    high, the prop ~50% of the frame height, the holder's face soft behind it."""
    k = ch.scale * ch.size_at(t)
    head = _head_now(ch, dg)
    front = facing(ch.base(t)[1])
    right = front.cross(Z).normalized()
    side = (1, -1)[k_i % 2]
    held = held_props(ch, t) if mode == "prop" else []
    obs = [o for a in held for o in ch.acc.get(a, []) if o.type in ("MESH", "FONT")]
    if not obs:
        if mode == "prop":
            print(f"[cam] insert: {ch.name} holds nothing at {t:.2f}s -> face")
        fov = 45.0
        th = math.tan(radians(fov) / 2)
        d = 1.55 * k / (0.78 * 2 * th)              # head + hair ~78% of the frame height
        dirv = (front + Z * 0.28 + right * side * 0.22).normalized()
        sp.update(pos=head + dirv * d, tgt=head - Z * 0.1 * k, fov=fov, push=0.05 * d, follow=None)
        return
    pts, grip = [], obs[0].parent
    for o in obs:
        mw = _wm(o, dg)
        pts += [mw @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    g3 = _wm(grip, dg).to_3x3() if grip is not None else None
    n = (g3 @ Vector((0, 0, -1))).normalized() if g3 else front
    n = Vector((n.x, n.y, 0)).normalized() if Vector((n.x, n.y, 0)).length > 0.2 else front
    if n.dot(front) < 0.3:                        # prop turned toward its holder (phone): look from the front
        n = front
    dirv = (n + Z * 0.34 + right * side * 0.18).normalized()       # ~19 deg above, a touch off-axis
    vr = dirv.cross(Z).normalized()
    vu = vr.cross(dirv).normalized()
    h = max(p.dot(vu) for p in pts) - min(p.dot(vu) for p in pts)
    w = max(p.dot(vr) for p in pts) - min(p.dot(vr) for p in pts)
    fov = 50.0
    th = math.tan(radians(fov) / 2)
    d = max(h / (0.45 * 2 * th), w / (0.75 * 2 * th * 9 / 16), 1.9 * k)
    tgt = c + (head - c) * 0.38                  # prop low in the frame, the face readable above it
    pos = c + dirv * d
    if (pos - head).length < 1.3 * k:             # never inside the holder's head
        pos = head + (pos - head).normalized() * 1.3 * k
    sp.update(pos=pos, tgt=tgt, fov=fov, push=0.06 * d, follow=None)
    print(f"[cam] insert {ch.name} {'+'.join(held)}: d={d:.2f} prop {h:.2f}x{w:.2f}")


def insert_cam(sp, ch, mode, t, dg, k_i, names=frozenset()):
    """Macro on the prop in ch's hand, or (mode "face") a tight close-up of the face: a long 42-44 deg lens from
    further back (no wide-angle bulge), slightly high. The whole head (hair included) stays in frame, the face
    close-up keeps a hint of shoulders and room. Tries both sides and a few heights / yaws and keeps the one
    whose head does not slice background text (signs, boards)."""
    k = ch.scale * ch.size_at(t)
    head = _head_now(ch, dg)
    box = _head_box(ch, dg, head, k)
    front = facing(ch.base(t)[1])
    right = front.cross(Z).normalized()
    side0 = (1, -1)[k_i % 2]
    held = held_props(ch, t) if mode == "prop" else []
    obs = [o for a in held for o in ch.acc.get(a, []) if o.type in ("MESH", "FONT")]
    skip = set(names) | {o.name for o in obs}
    if not obs:
        if mode == "prop":
            print(f"[cam] insert: {ch.name} holds nothing at {t:.2f}s -> face")
        fov = 44.0
        th = math.tan(radians(fov) / 2)
        hc = (box[0] + box[1]) / 2
        hh = box[1].z - box[0].z
        hw = max(box[1].x - box[0].x, box[1].y - box[0].y) * 0.85
        # head + hair ~44% of the frame height and <= ~72% of its width: shoulders and some room below / around
        d = max(hh / (0.44 * 2 * th), hw / (0.72 * 2 * th * 9 / 16))
        best = None
        for side in (side0, -side0):
            for el in (0.16, 0.06, 0.3):
                for yaw in (0.22, 0.42):
                    dirv = (front + Z * el + right * side * yaw).normalized()
                    pos = hc + dirv * d
                    tgt = hc - Z * 0.25 * th * d             # the head on the upper third
                    q = (tgt - pos).to_track_quat("-Z", "Y")
                    sc = 4 * _text_slice(dg, pos, q, th, box, skip) + abs(el - 0.16) + 0.15 * (yaw > 0.3) \
                        + 0.2 * (side != side0) + (5 if _first_hit(dg, pos, hc, skip, 0.85) else 0)
                    if best is None or sc < best[0]:
                        best = (sc, pos, tgt, side, el, yaw)
        sc, pos, tgt, side, el, yaw = best
        sp.update(pos=pos, tgt=tgt, fov=fov, push=0.05 * d, follow=None, focus=hc, focus_ch=ch)
        print(f"[cam] insert {ch.name} face: d={d:.2f} side {side} el {el} yaw {yaw} score {sc:.2f}")
        return
    pts, grip = [], obs[0].parent
    for o in obs:
        mw = _wm(o, dg)
        pts += [mw @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    g3 = _wm(grip, dg).to_3x3() if grip is not None else None
    n = (g3 @ Vector((0, 0, -1))).normalized() if g3 else front
    n = Vector((n.x, n.y, 0)).normalized() if Vector((n.x, n.y, 0)).length > 0.2 else front
    if n.dot(front) < 0.3:                        # prop turned toward its holder (phone): look from the front
        n = front
    fov = 42.0
    th = math.tan(radians(fov) / 2)
    top = Vector((head.x, head.y, box[1].z + 0.12 * k))
    best = None
    for side in (side0, -side0):
        for el in (0.34, 0.2, 0.52):
            for yaw in (0.18, 0.4):
                dirv = (n + Z * el + right * side * yaw).normalized()       # ~19 deg above, a touch off-axis
                vr = dirv.cross(Z).normalized()
                vu = vr.cross(dirv).normalized()
                h = max(p.dot(vu) for p in pts) - min(p.dot(vu) for p in pts)
                w = max(p.dot(vr) for p in pts) - min(p.dot(vr) for p in pts)
                d0 = d = max(h / (0.42 * 2 * th), w / (0.75 * 2 * th * 9 / 16), 1.9 * k)
                tgt = c + (head - c) * 0.38          # prop low in the frame, the face readable above it
                for _ in range(20):                  # the whole head (hair) in frame: aim up / over, then back off
                    pos = c + dirv * d
                    if (pos - head).length < 1.3 * k:     # never inside the holder's head
                        pos = head + (pos - head).normalized() * 1.3 * k
                    q = (tgt - pos).to_track_quat("-Z", "Y")
                    pt = _proj(pos, q, th, top)
                    ys = [p_[1] for p_ in (_proj(pos, q, th, p) for p in pts) if p_]
                    R = q @ Vector((1, 0, 0))
                    hc = (box[0] + box[1]) / 2
                    hw = 0.4 * max(box[1].x - box[0].x, box[1].y - box[0].y)
                    hx = [_proj(pos, q, th, hc + R * sg * hw) for sg in (-1, 1)]
                    bad = [p_[0] for p_ in hx if p_ is None or abs(p_[0]) > 0.97] if all(hx) else [9.0]
                    if bad:                          # head cut at the side: aim toward it, else back off
                        sg = 1 if bad[0] > 0 else -1
                        xs = [p_[0] for p_ in (_proj(pos, q, th, p) for p in pts) if p_]
                        if xs and max(-sg * x for x in xs) < 0.8:
                            tgt = tgt + R * sg * 0.1 * k
                        else:
                            d *= 1.06
                        continue
                    if pt is not None and pt[1] <= 0.9:
                        break
                    if ys and min(ys) > -0.8:
                        tgt = tgt + Z * 0.12 * k
                    else:
                        d *= 1.08
                sc = 4 * _text_slice(dg, pos, q, th, box, skip) + abs(el - 0.34) + 0.15 * (yaw > 0.3) \
                    + 0.2 * (side != side0) + 0.6 * (d / d0 - 1) \
                    + (5 if _first_hit(dg, pos, c, skip, 0.85) else 0)
                if best is None or sc < best[0]:
                    best = (sc, pos, tgt, d, h, w, side, el, yaw)
    sc, pos, tgt, d, h, w, side, el, yaw = best
    sp.update(pos=pos, tgt=tgt, fov=fov, push=0.06 * d, follow=None, focus=c, focus_ch=ch)
    print(f"[cam] insert {ch.name} {'+'.join(held)}: d={d:.2f} prop {h:.2f}x{w:.2f} side {side} el {el} yaw {yaw}"
          f" score {sc:.2f}")


POV_POSES = ("holdout", "phone", "carry", "hold", "hold1", "lookdown")   # props held low, away from the face


def _pose_name(ch, t):
    ps = [p for p in ch.poses if p[0] <= t]
    return max(ps, key=lambda p: p[0])[1] if ps else "idle"


def _held_pts(ch, t, dg, head, k, far=False):
    """(objects, world bound-box points) of the hand props ch holds at t. far=True keeps only the props held
    away from the face when there are others (a mic at the mouth is skipped for the book in the other hand)."""
    groups = []
    for a in held_props(ch, t):
        obs = [o for o in ch.acc.get(a, []) if o.type in ("MESH", "FONT")]
        pts = [_wm(o, dg) @ Vector(c) for o in obs for c in o.bound_box]
        if pts:
            groups.append((obs, pts))
    if far and len(groups) > 1:
        d = [((sum(p, Vector()) / len(p)) - head).length for _, p in groups]
        keep = [g for g, x in zip(groups, d) if x > 1.6 * k]
        groups = keep or [groups[d.index(max(d))]]
    return [o for g in groups for o in g[0]], [p for g in groups for p in g[1]]


def _box(pts):
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def _box_vis(pos, q, th, box):
    """Visible share (0..1) of a world box's screen rectangle inside the 9:16 frame (0 if behind the lens)."""
    cs = [Vector((x, y, z)) for x in (box[0].x, box[1].x) for y in (box[0].y, box[1].y) for z in (box[0].z, box[1].z)]
    pp = [_proj(pos, q, th, p) for p in cs]
    if any(p is None for p in pp):
        return 0.0
    x0, x1 = min(p[0] for p in pp), max(p[0] for p in pp)
    y0, y1 = min(p[1] for p in pp), max(p[1] for p in pp)
    vx = max(0.0, min(x1, 1) - max(x0, -1)) / max(1e-6, x1 - x0)
    vy = max(0.0, min(y1, 1) - max(y0, -1)) / max(1e-6, y1 - y0)
    return vx * vy


def _head_names(ch):
    return {ch.head.name} | {o.name for o in (getattr(ch, "hair", None) or [])}


def pov_cam(sp, ch, t, dg, names, all_char, indoor=True):
    """First-person view: from just behind / above ch's head (beside it, on the prop-hand side) looking down
    at the prop in their hand(s): the hands + prop in the lower half of the frame, the scene beyond on top,
    ~60 deg lens; a sliver of the holder's own hair / cheek may frame one edge (soft: the focus is the prop).
    Falls back to a top-down insert when they hold nothing."""
    k = ch.scale * ch.size_at(t)
    head = _head_now(ch, dg)
    obs, pts = _held_pts(ch, t, dg, head, k, far=True)
    if not obs:
        print(f"[cam] pov: {ch.name} holds nothing at {t:.2f}s -> top")
        return top_cam(sp, ch, t, dg, names, all_char)
    lo, hi = _box(pts)
    c = (lo + hi) / 2
    front = facing(ch.base(t)[1])
    right = front.cross(Z).normalized()
    pref = 1 if (c - head).dot(right) >= 0 else -1
    fov = 60.0
    th = math.tan(radians(fov) / 2)
    hn = _head_names(ch)
    skip = {o.name for o in obs} | {o.name for o in ch.hand}
    # the scene beyond: who ch is offering / showing it to (the nearest main character in front), if anyone
    tgt_ch, best_d = None, 25.0
    for o in Char.ALL:
        if o is ch or o.crowd or o.head_pos(t).z < -100:
            continue
        dv = o.base(t)[0] - ch.base(t)[0]
        dv.z = 0
        if 2.5 < dv.length < best_d and front.dot(dv.normalized()) > 0.35:        # within ~70 deg of ahead
            tgt_ch, best_d = o, dv.length
    th_o = _head_now(tgt_ch, dg) if tgt_ch else None
    best = None
    for side in (pref, -pref):
        for lat in (0.95, 1.3):
            for bk in (0.35, 0.9, 1.5):
                for up in (0.35, 0.75, 1.1):
                    pos = head + right * side * lat * k - front * bk * k + Z * up * k
                    hv = Vector((c.x - pos.x, c.y - pos.y, 0))
                    if hv.length < 1e-3:
                        continue
                    hdirs = [((hv.normalized() * 0.65 + front * 0.35).normalized(), 0)]
                    if th_o is not None:
                        ov = Vector((th_o.x - pos.x, th_o.y - pos.y, 0)).normalized()
                        hdirs += [(ov, 1), ((ov + hv.normalized()).normalized(), 1)]
                    hd_ = hv.length
                    e = math.atan2(c.z - pos.z, hd_)
                    if _first_hit(dg, head, pos, all_char):
                        continue                         # the camera is in / behind a wall
                    for hdir, looks in hdirs:
                        for yp in (0.42, 0.6):
                            pitch = max(radians(-62), min(radians(-6), e + math.atan(yp * th)))
                            dirv = hdir * cos(pitch) + Z * sin(pitch)
                            q = dirv.to_track_quat("-Z", "Y")
                            pc = _proj(pos, q, th, c)
                            if pc is None:
                                continue
                            ys = [p[1] for p in (_proj(pos, q, th, p) for p in pts) if p]
                            size = (max(ys) - min(ys)) / 2 if ys else 0.0
                            sc = 2 * max(0.0, pc[1] + 0.25) + 2 * max(0.0, -0.75 - pc[1])                                 + 1.5 * max(0.0, abs(pc[0]) - 0.55) + 3 * max(0.0, 0.16 - size)                                 + 2 * max(0.0, size - 0.5) + 0.25 * (side != pref) + 0.1 * abs(up - 0.75)
                            if th_o is not None:         # their face in the top half, or it is not a look at them
                                po = _proj(pos, q, th, th_o)
                                sc += 0.8 if not looks else 0.0
                                if po is None or not (-0.05 < po[1] < 0.85 and abs(po[0]) < 0.85):
                                    sc += 1.0
                                elif _first_hit(dg, pos, th_o, skip | names, 0.9):
                                    sc += 0.8
                            hit = _first_hit(dg, pos, c, skip, 0.9)
                            if hit:
                                sc += 2 if hit[1] in names else 6
                            if best is not None and sc >= best[0]:
                                continue
                            # own head / hair a sliver at most; nothing else (the mic at the mouth, an arm) at the lens
                            area, _, clut = _frac_on(dg, pos, q, th, hn, 0.55 * (c - pos).length, skip, nx=8, ny=14)
                            sc += 6 * max(0.0, area - 0.14) + 10 * max(0.0, clut - 0.05)
                            out_ = _sees_out(dg, pos, q, th) if indoor else 0.0
                            sc += 0.8 * out_                 # (real look: the front wall closes the room)
                            if os.environ.get("MILO_CAMDBG"):
                                print(f"[dbg] pov s{side} lat{lat} bk{bk} up{up} look{looks} yp{yp} pc({pc[0]:.2f},"
                                      f"{pc[1]:.2f}) size {size:.2f} area {area:.2f} clut {clut:.2f} out {out_:.2f}"
                                      f" hit {hit[1] if hit else '-'} -> {sc:.2f}")
                            if best is None or sc < best[0]:
                                best = (sc, pos, dirv, side, lat, bk, up, area, size, clut, looks)
    if best is None or best[0] > 2.0:
        print(f"[cam] pov {ch.name}: no clean first-person view (score {best[0] if best else 99:.2f}) -> top")
        return top_cam(sp, ch, t, dg, names, all_char)
    sc, pos, dirv, side, lat, bk, up, area, size, clut, looks = best
    d = (c - pos).length
    sp.update(pos=pos, tgt=pos + dirv * d, fov=fov, push=0.04 * d, follow=None, focus=c, focus_ch=ch)
    print(f"[cam] pov {ch.name}: side {side} lat {lat} back {bk} up {up} prop {size:.2f} own head {area:.2f}"
          f" near clutter {clut:.2f}{' at ' + tgt_ch.name if looks else ''} score {sc:.2f}")


def top_cam(sp, ch, t, dg, names, all_char):
    """Top-down insert: straight down (~75 deg) on the prop in ch's hand(s), the holder's head at the top edge;
    with no prop, the character from above (whole figure, ~72 deg)."""
    k = ch.scale * ch.size_at(t)
    head = _head_now(ch, dg)
    obs, pts = _held_pts(ch, t, dg, head, k)
    front = facing(ch.base(t)[1])
    fov = 50.0
    th = math.tan(radians(fov) / 2)
    hn = _head_names(ch)
    skip = {o.name for o in obs} | {o.name for o in ch.hand}
    if obs:
        lo, hi = _box(pts)
        c = (lo + hi) / 2
        span = max(hi.x - lo.x, hi.y - lo.y, 0.6 * k)
        tgt0 = c + (Vector((head.x, head.y, c.z)) - c) * 0.12
    else:
        c = ch.base(t)[0] + Z * (2.4 * k + ch.lift_at(t))
        span = 3.2 * k
        tgt0 = c
    best = None
    for yaw in (0, 30, -30, 55, -55):
        n = Quaternion((0, 0, 1), radians(yaw)) @ front
        for el in (76, 66, 84):
            dirv = n * cos(radians(el)) + Z * sin(radians(el))
            d = max(span / (0.42 * 2 * th * 9 / 16), (2.4 if obs else 6.5) * k)
            pos = c + dirv * d
            clip = _first_hit(dg, c, pos, all_char | skip)      # ceiling / lamp above: come down under it
            if clip:
                d = clip[0] - 0.5
                pos = c + dirv * d
            if d < 1.6 * k:
                continue
            q = (tgt0 - pos).to_track_quat("-Z", "Y")
            sc = abs(yaw) / 120 + abs(el - 76) / 40 + (1.5 if clip else 0)
            hit = _first_hit(dg, pos, c, skip, 0.92)
            if hit:
                sc += 2 if hit[1] in names else 6
            if best is not None and sc >= best[0]:
                continue
            area = _frac_on(dg, pos, q, th, hn, nx=8, ny=14)[0] if obs else 0.0
            sc += 5 * max(0.0, area - 0.18)
            if best is None or sc < best[0]:
                best = (sc, pos, yaw, el, d, area)
    if best is None:
        best = (9, c + Z * 4 * k + front * 1.2 * k, 0, 72, 4 * k, 0)
    sc, pos, yaw, el, d, area = best
    sp.update(pos=pos, tgt=tgt0, fov=fov, push=0.05 * d, follow=None, focus=c, focus_ch=ch)
    print(f"[cam] top {ch.name}{' (no prop)' if not obs else ''}: yaw {yaw} el {el} d={d:.2f} head {area:.2f}"
          f" score {sc:.2f}")


def _sees_out(dg, pos, q, th):
    """Share of the frame's upper part that looks out of the set (nothing hit, or only far outside ground)."""
    n = out = 0
    for gy in (0.97, 0.65, 0.3, -0.05):
        for gx in (-0.9, -0.45, 0.0, 0.45, 0.9):
            r = q @ Vector((gx * th * 9 / 16, gy * th, -1)).normalized()
            if r.z > 0.3:                              # steeply up: an open roof is fine
                continue
            ok, loc, *_ = SC.ray_cast(dg, pos, r, distance=400)
            n += 1
            out += not ok or (loc - pos).length > 50
    return out / max(1, n)


def ots_cam(sp, a, b, t, dg, skip, side0, indoor=True):
    """Over a's shoulder onto b: a's head/shoulder a dark shape on one side (~40% of the frame height),
    b's face on the opposite third. Tries both shoulders; walls pull the camera in, other people flip sides."""
    ka, kb = a.scale * a.size_at(t), b.scale * b.size_at(t)
    ha, hb = _head_now(a, dg), _head_now(b, dg)
    dh = Vector((hb.x - ha.x, hb.y - ha.y, 0))
    D = max(dh.length, 1.5)
    u = dh.normalized() if dh.length > 1e-3 else -facing(a.base(t)[1])
    r = u.cross(Z).normalized()
    th = min(max((3.6 * kb - 1.625 * ka) / D, math.tan(radians(16))), math.tan(radians(30)))
    B0 = 1.625 * ka / th
    best = None
    for side in (side0, -side0):
        B = B0
        for it in range(3):
            th_h = th * 9 / 16
            gap = math.atan(th_h / 3) + math.atan(0.7 * th_h)
            Lmax = math.sqrt(B * (B + D))
            lo_, hi_ = 0.0, Lmax
            for _ in range(40):
                L = (lo_ + hi_) / 2
                if math.atan(L / B) - math.atan(L / (B + D)) < gap:
                    lo_ = L
                else:
                    hi_ = L
            L = (lo_ + hi_) / 2
            pos = ha + r * side * L - u * B + Z * 0.35 * ka
            # walls / furniture behind a: pull in (a gets bigger), at most to 2.4 units
            hit = _first_hit(dg, ha + Z * 0.35 * ka, pos, skip)
            if hit and it < 2 and B > 2.4 * ka:
                B = max(2.4 * ka, B * (hit[0] - 0.5) / (pos - ha).length)
                th = min(max(th, 1.625 * ka / B), math.tan(radians(36)))    # keep a's head ~40% of the frame
                continue
            break
        ab = math.atan2(-side * L, B + D)               # b's angle from u (positive = right)
        psi = ab - side * math.atan(th_h / 3)          # b on the third opposite a (a lands at x = -0.7 side)
        vh = u * cos(psi) + r * sin(psi)
        hd_ = math.hypot(B + D, L)
        # indoor sets are open toward the default camera: a reverse angle may look down rather than out
        # (up to 3 steps up; keeps the lowest step that sees least of the outside)
        levels = []
        for it in range(4 if indoor else 1):
            p_ = pos + Z * 0.7 * ka * it
            phi = math.atan2(hb.z - p_.z, hd_) - math.atan(0.16 * th)
            dirv = vh * cos(phi) + Z * sin(phi)
            out_ = _sees_out(dg, p_, dirv.to_track_quat("-Z", "Y"), th) if indoor else 0.0
            levels.append((out_ + 0.04 * it, it, p_, dirv))
            if out_ <= 0.05:
                break
        _, raised, pos, dirv = min(levels, key=lambda x: x[0])
        blocked = _first_hit(dg, pos, hb, skip, 0.95)
        wall = _first_hit(dg, ha + Z * 0.35 * ka, pos, skip)
        score = (1 if blocked else 0) + (1 if wall else 0)
        cand = (score, side, pos, pos + dirv * hd_, 2 * math.degrees(math.atan(th)), B, L, blocked, raised)
        if best is None or score < best[0]:
            best = cand
        if score == 0:
            break
    score, side, pos, tgt, fov, B, L, blocked, raised = best
    sp.update(pos=pos, tgt=tgt, fov=fov, push=0.03 * (tgt - pos).length, follow=None, roll=sp.get("roll", 0.0))
    print(f"[cam] ots {a.name}->{b.name}: side {side} B={B:.1f} L={L:.1f} fov={fov:.0f} raised {raised}"
          f"{' BLOCKED ' + blocked[1] if blocked else ''}")


def _frac_on(dg, pos, q, th, names, near=0.0, other=(), floor_z=None, nx=10, ny=18):
    """Share of the frame (area, widest row) whose first visible surface belongs to names, and the share
    that is foreground clutter: anything else (not in other, not floor) closer than near."""
    tot = widest = clut = 0
    for gy in range(ny):
        n = 0
        for gx in range(nx):
            r = q @ Vector((((gx + 0.5) / nx * 2 - 1) * th * 9 / 16, ((gy + 0.5) / ny * 2 - 1) * th, -1))
            hit = _first_hit(dg, pos, pos + r.normalized() * 150, (), floor_z=floor_z)
            if hit and hit[1] in names:
                n += 1
            elif hit and hit[0] < near and hit[1] not in other:
                clut += 1
        tot += n
        widest = max(widest, n)
    return tot / (nx * ny), widest / nx, clut / (nx * ny)


def _width_est(pos, q, th, boxes):
    """Cheap estimate of the frame width share covered by a set of objects (their projected bound boxes)."""
    R, U, F = q @ Vector((1, 0, 0)), q @ Vector((0, 1, 0)), q @ Vector((0, 0, -1))
    ivs = []
    for cs in boxes:
        xs, ys = [], []
        for p in cs:
            d = p - pos
            z = d.dot(F)
            if z <= 0.05:
                break
            xs.append(d.dot(R) / (z * th * 9 / 16))
            ys.append(d.dot(U) / (z * th))
        else:
            if max(ys) < -1 or min(ys) > 1:
                continue
            x0, x1 = max(min(xs), -1.0), min(max(xs), 1.0)
            if x1 > x0:
                ivs.append((x0, x1))
    tot, end = 0.0, -1.0
    for x0, x1 in sorted(ivs):
        if x1 > end:
            tot += x1 - max(x0, end)
            end = x1
    return tot / 2


def _ots_L(B, D, gap):
    """Sideways offset that puts a (B in front) and b (B + D in front) gap radians apart."""
    lo_, hi_ = 0.0, math.sqrt(B * (B + D))
    for _ in range(40):
        L = (lo_ + hi_) / 2
        if math.atan(L / B) - math.atan(L / (B + D)) < gap:
            lo_ = L
        else:
            hi_ = L
    return (lo_ + hi_) / 2


def ots_cam_real(sp, a, b, t, dg, skip, side0, indoor=True, a_names=frozenset()):
    """Real look over a's shoulder onto b: b's face just under the upper third on one side, b's figure ~half
    the frame height (a longer lens the farther apart they stand); a's head / shoulder pushed to the opposite
    frame edge (head centre x ~ 0.9..1.5 of the half-width, partly cropped), a bit lower than b and
    ray-measured to <= ~25% of the frame width - a framing edge, never a foreground blob. Searches the lens,
    both shoulders, a's screen position, the distance behind a (walls clip it) and the camera height; another
    person in the way, a wall, foreground furniture, or the outside of an indoor set cost score."""
    ka, kb = a.scale * a.size_at(t), b.scale * b.size_at(t)
    ha, hb = _head_now(a, dg), _head_now(b, dg)
    dh = Vector((hb.x - ha.x, hb.y - ha.y, 0))
    D = max(dh.length, 1.5)
    u = dh.normalized() if dh.length > 1e-3 else -facing(a.base(t)[1])
    r = u.cross(Z).normalized()
    fz = a.base(t)[0].z
    yb = 0.24
    boxA = _head_box(a, dg, ha, ka)
    boxes = []
    for nm in a_names:
        ob = core.bpy.data.objects.get(nm)
        if ob is not None and ob.type == "MESH" and not _hidden(ob):
            mw = _wm(ob, dg)
            boxes.append([mw @ Vector(c) for c in ob.bound_box])
    cands, seen = [], set()
    for fov in (46.0, 38.0, 31.0, 25.0, 20.0):
        th = math.tan(radians(fov) / 2)
        th_h = th * 9 / 16
        for side in (side0, -side0):
            for xa in (0.72, 0.85, 0.95, 1.08, 1.25):     # a's head centre: at the edge, never cropped away
                gap = math.atan(th_h / 3) + math.atan(xa * th_h)
                s_ = math.tan(math.pi / 4 + gap / 2)
                Bmax = min(24 * ka, D / max(1e-3, s_ * s_ - 1))      # farther back and a / b line up
                for bf in (1.0, 0.8, 0.6):
                    B, clip = max(2.0 * ka, bf * Bmax), False
                    for it in range(2):
                        L = _ots_L(B, D, gap)
                        pos = ha + r * side * L - u * B
                        hit = _first_hit(dg, ha + Z * 0.35 * ka, pos + Z * 0.35 * ka, skip)
                        if hit and it == 0 and B > 2.0 * ka:
                            B, clip = max(2.0 * ka, B * (hit[0] - 0.6) / (pos - ha).length), True
                            continue
                        break
                    key = (fov, side, xa, round(B, 1))
                    if key in seen:
                        continue
                    seen.add(key)
                    ab = math.atan2(-side * L, B + D)          # b's angle from u (positive = right)
                    psi = ab - side * math.atan(th_h / 3)       # b on the third opposite a
                    vh = u * cos(psi) + r * sin(psi)
                    hd_ = math.hypot(B + D, L)
                    bsz = 6.3 * kb / (2 * hd_ * th)             # b's figure / frame height
                    for ez in ((0.7, 1.4, 2.3, 3.4) if indoor else (0.7, 1.4, 2.3)):
                        p_ = pos + Z * ez * ka
                        phi = math.atan2(hb.z - p_.z, hd_) - math.atan(yb * th)
                        dirv = vh * cos(phi) + Z * sin(phi)
                        q = dirv.to_track_quat("-Z", "Y")
                        pa = _proj(p_, q, th, ha)
                        ya = pa[1] if pa else -1.0
                        pf = _proj(p_, q, th, a.base(t)[0])
                        cheap = 6 * max(0.0, 0.40 - bsz) + 2 * max(0.0, bsz - 0.85) \
                            + 0.6 * max(0.0, ya - (yb - 0.2)) + 0.4 * (1 - bf) + 0.15 * abs(ez - 1.4) \
                            + 0.15 * (side != side0) + 0.12 * (xa - 0.95) \
                            + (1.0 if pa is None or abs(pa[0]) > 1.15 or not -1.05 < pa[1] < 1 else 0) \
                            + (0.6 if pf and abs(pf[0]) < 1 and pf[1] > -1 else 0)  # head at the edge, not a full figure
                        wa = _width_est(p_, q, th, boxes)
                        cheap += 8 * max(0.0, wa - 0.34) + 8 * max(0.0, 0.1 - wa)
                        # the foreground reads as a's head + shoulder: at least ~45% of the head (hair) in frame
                        cheap += 7 * max(0.0, 0.45 - _box_vis(p_, q, th, boxA))
                        cands.append((cheap, fov, th, side, xa, bf, B, L, ez, p_, dirv, hd_, bsz, clip))
    # the ray-heavy checks only for the cheapest geometries, best first
    import time
    best, n_eval, t_0 = None, 0, time.time()
    for cheap, fov, th, side, xa, bf, B, L, ez, p_, dirv, hd_, bsz, clip in sorted(cands, key=lambda c: c[0]):
        if best is not None and (cheap >= best[0] or n_eval >= 30):
            break
        n_eval += 1
        blocked = _first_hit(dg, p_, hb, skip, 0.95)
        wall = _first_hit(dg, ha + Z * 0.35 * ka, p_, skip)
        cheap += (6 if blocked else 0) + (3 if wall else 0)
        if best is not None and cheap >= best[0]:
            continue
        q = dirv.to_track_quat("-Z", "Y")
        out_ = _sees_out(dg, p_, q, th) if indoor else 0.0
        area, wide, clut = _frac_on(dg, p_, q, th, a_names, 0.85 * math.hypot(B, L), skip,
                                    (fz + 0.4 * ka, p_.z + 1.0))
        score = cheap + 4 * out_ + 8 * max(0.0, wide - 0.32) + 8 * max(0.0, 0.14 - wide) \
            + 6 * max(0.0, area - 0.18) + 30 * max(0.0, 0.04 - area) + 6 * max(0.0, clut - 0.04)
        if os.environ.get("MILO_CAMDBG"):
            print(f"[dbg] fov {fov:.0f} s {side} xa {xa} bf {bf} ez {ez} B {B:.1f} cheap {cheap:.2f} out {out_:.2f}"
                  f" area {area:.2f} wide {wide:.2f} clut {clut:.2f} b {bsz:.2f} -> {score:.2f}"
                  f"{' blocked' if blocked else ''}{' wall' if wall else ''}")
        if best is None or score < best[0]:
            best = (score, side, p_, p_ + dirv * hd_, B, L, xa, ez, area, wide, clut, bsz, fov, blocked, clip)
    score, side, pos, tgt, B, L, xa, ez, area, wide, clut, bsz, fov, blocked, clip = best
    th = math.tan(radians(fov) / 2)
    q = (tgt - pos).to_track_quat("-Z", "Y")
    hvis = _box_vis(pos, q, th, boxA)
    harea = _frac_on(dg, pos, q, th, _head_names(a) & set(a_names), nx=12, ny=20)[0]
    if blocked or hvis < 0.3 or harea < 0.006:
        # no readable head + shoulder for a (only an arm / a sliver at the edge): a clean single on b instead
        print(f"[cam] ots {a.name}->{b.name}: head vis {hvis:.2f} area {harea:.3f}"
              f"{' blocked' if blocked else ''} -> clean single")
        return _clean_single(sp, a, b, t, dg, skip, a_names)
    sp.update(pos=pos, tgt=tgt, fov=fov, push=0.03 * (tgt - pos).length, follow=None, roll=sp.get("roll", 0.0))
    print(f"[cam] ots {a.name}->{b.name}: fov {fov:.0f} side {side} D={D:.1f} B={B:.1f}{' (wall)' if clip else ''}"
          f" L={L:.1f} xa={xa} ez={ez} fg area {area:.2f} width {wide:.2f} clutter {clut:.2f} b {bsz:.2f}"
          f" score {score:.2f} ({n_eval} ray-checked, {time.time() - t_0:.1f}s) head vis {hvis:.2f} area {harea:.3f}"
          f"{' BLOCKED ' + blocked[1] if blocked else ''}")


def _clean_single(sp, a, b, t, dg, skip, a_names):
    """OTS fallback: a clean medium close-up of b from a's side (a just out of frame), 44 deg lens."""
    kb = b.scale * b.size_at(t)
    hb = _head_now(b, dg)
    box = _head_box(b, dg, hb, kb)
    hc = (box[0] + box[1]) / 2
    u = Vector((_head_now(a, dg).x - hb.x, _head_now(a, dg).y - hb.y, 0))
    u = u.normalized() if u.length > 1e-3 else facing(b.base(t)[1])
    fov = 44.0
    th = math.tan(radians(fov) / 2)
    d = (box[1].z - box[0].z) / (0.3 * 2 * th)       # head + hair ~30% of the frame: a medium close-up
    best = None
    for yaw in (22, -22, 36, -36, 50, -50):
        dirv = (Quaternion((0, 0, 1), radians(yaw)) @ u + Z * 0.1).normalized()
        pos = hc + dirv * d
        tgt = hc - Z * 0.3 * th * d
        q = (tgt - pos).to_track_quat("-Z", "Y")
        sc = abs(yaw) / 60 + (6 if _first_hit(dg, pos, hc, skip, 0.92) else 0) \
            + (4 if _first_hit(dg, hc, pos, skip) else 0)
        if best is not None and sc >= best[0]:
            continue
        sc += 20 * _frac_on(dg, pos, q, th, a_names, nx=8, ny=14)[0]
        if best is None or sc < best[0]:
            best = (sc, pos, tgt, yaw)
    sc, pos, tgt, yaw = best
    sp.update(pos=pos, tgt=tgt, fov=fov, push=0.03 * d, follow=None, roll=sp.get("roll", 0.0), single=True)
    print(f"[cam] single on {b.name} (from {a.name}'s side): yaw {yaw} d={d:.1f} score {sc:.2f}")


OUTDOOR = ("street", "farm", "sky")


def post_cams(C, specs):
    """Place every insert / OTS shot on the animated scene (call after write_motion)."""
    bpy = core.bpy
    names = {c.name: {c.root.name} | {o.name for o in c.root.children_recursive} for c in Char.ALL}
    n_ins = 0
    for i, (s, sp) in enumerate(zip(SHOTS, specs)):
        post = sp.get("post")
        if not post:
            continue
        t = sp["t_ref"]
        SC.frame_set(frame(t))
        dg = bpy.context.evaluated_depsgraph_get()
        real = REALCAM
        if post[0] in ("prop", "face"):
            if real:
                insert_cam(sp, C[post[1]], post[0], t, dg, n_ins, names[post[1]])
            else:
                insert_cam_brand(sp, C[post[1]], post[0], t, dg, n_ins)
            n_ins += 1
        elif post[0] in ("pov", "top"):
            all_char = set().union(*names.values())
            if post[0] == "pov":
                pov_cam(sp, C[post[1]], t, dg, names[post[1]], all_char, s["set"] not in OUTDOOR)
            else:
                top_cam(sp, C[post[1]], t, dg, names[post[1]], all_char)
        else:
            a, b = C[post[1]], C[post[2]]
            if real:
                ots_cam_real(sp, a, b, t, dg, names[a.name] | names[b.name], sp.get("side", 1),
                             s["set"] not in OUTDOOR, names[a.name])
            else:
                ots_cam(sp, a, b, t, dg, names[a.name] | names[b.name], sp.get("side", 1), s["set"] not in OUTDOOR)
        if REALCAM:      # same slow push as the other character shots
            dur = (s["t1"] - s["t0"]) * sp["end"]
            rate = (0.05 if post[0] != "ots" else 0.025) * (BRICK_CFG["push"] if BRICK else 1.0)
            sp["push"] = (sp["tgt"] - sp["pos"]).length * (1 - 1 / (1 + rate * dur))


def cam_pose(s, sp, t):
    """Camera (pos, quat, fov) of shot s / spec sp at time t."""
    u = core.smooth((t - s["t0"]) / max(1e-6, (s["t1"] - s["t0"]) * sp["end"]))
    pos = sp["pos"] + sp["slide"] * u
    tgt = sp["tgt"] + sp["slide"] * u
    pos = pos + (tgt - pos).normalized() * sp["push"] * u
    if sp["follow"]:          # tilt with anything rising so heads never leave the frame
        rise = sp["follow"].head_pos(t).z - sp["follow"].head_pos(sp["t_ref"]).z
        if 0 < rise < 50:
            tgt = tgt + Vector((0, 0, rise))
            pos = pos + Vector((0, 0, rise * 0.5))
    q = (tgt - pos).to_track_quat("-Z", "Y")
    if sp["roll"]:
        q = q @ Quaternion((0, 0, 1), radians(sp["roll"]))
    fov = sp["fov"]
    if sp.get("punch", 1.0) != 1.0:      # zoom punch: 1.0 -> punch over ~2.5 frames, starting 1 frame in, holds
        z = 1 + (sp["punch"] - 1) * core.smooth(((t - s["t0"]) * 30 - 1) / 2.5)
        fov = 2 * math.degrees(math.atan(math.tan(radians(fov) / 2) / z))
    return pos, q, fov


def camera_frames(specs):
    out = []
    starts = [frame(s["t0"]) for s in SHOTS]
    k = 0
    for f in range(NF):
        while k + 1 < len(SHOTS) and starts[k + 1] <= f:
            k += 1
        out.append(cam_pose(SHOTS[k], specs[k], f / 30) + (k,))
    return out


# ---------------------------------------------------------------- "real" camera grammar (top animated Shorts channels)
DUTCH_BEATS = ("INC", "POP", "ESC", "TWIST")             # panic / comic beats get a 8-15 deg Dutch tilt
LOW_BEATS = ("ESC", "REVEAL", "TWIST", "ME", "INC", "RULE", "PAYOFF", "CALLBACK")   # looking up = bigger
HIGH_BEATS = ("POP", "QUIET", "VICTIM", "CAUSE", "EX")   # looking down = smaller, caught out
PUNCH_BEATS = ("POP", "TWIST", "PAYOFF")
Z = Vector((0, 0, 1))


EYE = ("close", "med", "two")         # framings that read "eye-level medium" unless angled
REAL_LENS = {"close": 46.0, "med": 58.0, "two": 60.0, "low": 58.0, "high": 58.0}   # vertical FOV; wides 70


def _low_frame(sp, ch, t, close):
    """Hero low angle that fills the frame: the camera near the floor (close: chest height), the head top at
    y ~0.74 and the feet (close: the belt) on the bottom edge, the upward tilt capped at 20 deg so the ceiling /
    sky stays a band above the head (<= ~25% of the frame). Keeps the spec's side of the subject."""
    k = ch.scale * ch.size_at(t)
    fz = ch.base(t)[0].z + ch.lift_at(t)
    v = sp["pos"] - sp["tgt"]
    hz = Vector((v.x, v.y, 0))
    hz = hz.normalized() if hz.length > 1e-3 else facing(ch.base(t)[1])
    th = math.tan(radians(sp["fov"]) / 2)
    if close:
        zb, zt, cz, yb = fz + 2.5 * k, fz + 6.5 * k, fz + 2.1 * k, -0.95
    else:
        zb, zt, cz, yb = fz - 0.1 * k, fz + 6.5 * k, fz + 0.8 * k, -0.9
    yt = 0.74
    want = math.atan(yt * th) - math.atan(yb * th)
    lo_, hi_ = 0.3 * k, 100 * k
    for _ in range(50):
        d = (lo_ + hi_) / 2
        if math.atan2(zt - cz, d) - math.atan2(zb - cz, d) > want:
            lo_ = d
        else:
            hi_ = d
    p = math.atan2(zt - cz, d) - math.atan(yt * th)
    if p > radians(20):                 # too steep: keep the head top in place, let the feet / belt go
        p = radians(20)
        d = (zt - cz) / math.tan(p + math.atan(yt * th))
    head = ch.head_pos(t)
    pos = Vector((head.x, head.y, cz)) + hz * d
    sp["pos"], sp["tgt"] = pos, pos + (-hz * cos(p) + Z * sin(p)) * d


def _convert(i, s, C, t, prev):
    """The 3rd eye-level close/med/two in a row becomes a prop shot (the subject holds a prop: pov / top when it
    is held low, else an insert) or an OTS (someone faces the subject and the subject faces them). Returns
    (preset, who) or None (the caller angles it)."""
    who = [w for w in (s["who"] or "").split(",") if w in C and w != "_crowd"]
    if not who or s["beat"] == "ME" or i == len(SHOTS) - 1:
        return None
    if len(who) == 2:
        a, b = C[who[0]], C[who[1]]
        pa, pb = a.base(t)[0], b.base(t)[0]
        d = pb - pa
        if d.length > 0.5 and facing(a.base(t)[1]).dot(d.normalized()) > 0.2 \
                and facing(b.base(t)[1]).dot(-d.normalized()) > 0.2 and prev != "ots":
            return "ots", f"{who[0]},{who[1]}"
        return None
    ch = C[who[0]]
    if held_props(ch, t) and prev not in ("insert", "pov", "top"):
        # a prop held low (offered, read, carried): first-person or top-down; held up by the face: macro insert
        if _pose_name(ch, t) in POV_POSES:
            return ("pov", "top")[_h(s["name"]) % 2], who[0]
        return "insert", who[0]
    if prev == "ots":
        return None
    p = ch.base(t)[0]
    best = None
    for o in chars_in(C, s["set"], t):
        if o is ch or o.crowd or o.head_pos(t).z < -100:
            continue
        d = o.base(t)[0] - p
        if not 1.5 < d.length < 18:
            continue
        if facing(ch.base(t)[1]).dot(d.normalized()) > 0.3 and facing(o.base(t)[1]).dot(-d.normalized()) > 0.2:
            if best is None or d.length < best[0]:
                best = (d.length, o.name)
    return ("ots", f"{best[1]},{who[0]}") if best else None


def real_grammar(specs, C, S):
    """Remap every spec to the 62-70 deg wide lens, then vary the angle shot by shot (deterministic).
    Never more than 2 eye-level close / med / two shots in a row: the 3rd becomes an insert, an OTS or low/high."""
    gap, n_ext, rsign, last_roll, punched = 2, 0, 1, False, set()
    run, prev = 0, None
    last = len(SHOTS) - 1
    for i, s in enumerate(SHOTS):
        sp = specs[i]
        cam, beat, h, t = sp.get("preset", s["cam"]), s["beat"], _h(s["name"]), sp["t_ref"]
        who = [w for w in (s["who"] or "").split(",") if w in C and w != "_crowd"]
        solo = cam in ("close", "med") and len(who) == 1
        # 1. an extreme angle every ~4-6 shots: low (near the floor, looking up) or high / top-down
        gap += 1
        kind = "eye"
        if solo and i != last:
            want = 4 if beat in ("ESC", "TWIST", "REVEAL", "POP", "QUIET") else 5 + h % 2
            if gap >= want:
                kind = "low" if beat in LOW_BEATS else "high" if beat in HIGH_BEATS else ("low", "high")[n_ext % 2]
                if kind == "high" and cam == "med" and (h >> 3) % 2 and s["set"] in OUTDOOR:   # no room under a ceiling
                    kind = "top"
                gap, n_ext = 0, n_ext + 1
        # 2. a 3rd eye-level close/med in a row: insert / OTS, or else low / high
        if cam in EYE and kind == "eye" and run >= 2:
            conv = _convert(i, s, C, t, prev)
            if conv:
                sp = cam_for(dict(s, cam=conv[0], who=conv[1]), i, C, S)
                sp["t_ref"] = t
                specs[i] = sp
                print(f"[cam] {s['name']}: 3rd eye-level in a row -> {conv[0]}:{conv[1]}")
                cam = conv[0]
            elif who:
                kind = "low" if beat in LOW_BEATS else "high" if beat in HIGH_BEATS else ("low", "high")[n_ext % 2]
                gap, n_ext = 0, n_ext + 1
                print(f"[cam] {s['name']}: 3rd eye-level in a row -> {kind}")
        run = run + 1 if cam in EYE and kind == "eye" else 0
        prev = cam
        if sp.get("post"):                      # insert / OTS: placed on the posed scene by post_cams()
            sp["subj"], sp["angle"] = [], cam
        else:
            sp["subj"] = [C[w] for w in who] if cam != "slide" and not (cam == "wide" and s["who"] in (None, "set")) else []
            # same framing at the target, camera moved along its line for the lens: long on close-ups (no
            # wide-angle bulge on faces), normal on mediums / two-shots / lows / highs, extra-wide on wides
            lens_tab = BRICK_CFG["lens"] if BRICK else REAL_LENS      # brick: 35-50 mm-ish, placed close
            new = lens_tab.get(cam, 70.0)
            if sp["fov"] != new and (sp["fov"] < new or cam in lens_tab):
                k = math.tan(radians(sp["fov"]) / 2) / math.tan(radians(new) / 2)
                if cam == "close":
                    k *= 1.4                                 # a looser MCU: whole head + hair, chest in
                    sp["tgt"] = sp["tgt"] + Vector((0, 0, 0.15))
                sp["pos"] = sp["tgt"] + (sp["pos"] - sp["tgt"]) * k
                sp["push"] *= k
                sp["fov"] = new
            if cam == "low" and len(who) == 1:
                _low_frame(sp, C[who[0]], t, False)
            if kind == "low" and len(who) == 1:
                _low_frame(sp, C[who[0]], t, cam == "close")
            elif kind != "eye":
                ch = C[who[0]]
                k = ch.scale * ch.size_at(t)
                feet_z = ch.base(t)[0].z + ch.lift_at(t)
                v = sp["pos"] - sp["tgt"]
                dist = v.length
                hz = Vector((v.x, v.y, 0))
                hz = hz.normalized() if hz.length > 1e-3 else facing(ch.base(t)[1])
                e = radians({"low": -21 if cam == "close" else -17, "high": 36, "top": 70}[kind])
                if kind == "low" and cam != "close":
                    sp["tgt"] = sp["tgt"] + Vector((0, 0, 0.5 * k))     # look up, keep the head clear of the top
                if kind == "top":
                    dist *= 1.15
                sp["pos"] = sp["tgt"] + hz * dist * cos(e) + Z * dist * sin(e)
                if sp["pos"].z < feet_z + 0.6 * k:
                    sp["pos"].z = feet_z + 0.6 * k
            sp["angle"] = kind
            # 3. rule of thirds: the subject sits on the third away from where they look (lead room)
            if solo and kind != "top" and beat != "ME" and i != last:
                ch = C[who[0]]
                d = sp["tgt"] - sp["pos"]
                right = d.normalized().cross(Z)
                if right.length > 1e-3:
                    right.normalize()
                    look_ = facing(ch.base(t)[1]).dot(right)
                    sgn = 1 if look_ > 0.15 else -1 if look_ < -0.15 else (1, -1)[i % 2]
                    sp["tgt"] = sp["tgt"] + right * sgn * d.length * math.tan(radians(sp["fov"]) / 2) * 9 / 16 / 3
        # 4. Dutch tilt on panic / comic beats (never two in a row)
        if cam in ("close", "med", "two", "low", "high", "ots") and beat in DUTCH_BEATS and not last_roll:
            sp["roll"] = rsign * (8 + h % 8)
            rsign, last_roll = -rsign, True
        else:
            sp["roll"], last_roll = 0.0, False
        # 5. slow push: ~5%/s on reactions (close, QUIET, REVEAL), ~2.5%/s otherwise (inserts / OTS: post_cams)
        if cam in ("close", "med", "two", "low", "high"):
            dur = (s["t1"] - s["t0"]) * sp["end"]
            rate = (0.05 if cam == "close" or beat in ("QUIET", "REVEAL") else 0.025) * \
                (BRICK_CFG["push"] if BRICK else 1.0)
            sp["push"] = (sp["tgt"] - sp["pos"]).length * (1 - 1 / (1 + rate * dur))
        # 6. zoom punch on the first shot of each POP / TWIST / PAYOFF line
        if beat in PUNCH_BEATS and s["line"] not in punched and cam != "slide":
            punched.add(s["line"])
            sp["punch"] = 1.08
        # 7. the whole head (hair included) stays in frame through the push / punch / Dutch tilt: aim up a bit
        if cam in ("close", "med", "low", "high") and len(who) == 1 and not sp.get("post"):
            ch = C[who[0]]
            k = ch.scale * ch.size_at(t)
            for _ in range(10):
                worst = -9.0
                for tt in (t, s["t1"] - 0.02):
                    p, q, fov = cam_pose(s, sp, tt)
                    th = math.tan(radians(fov) / 2)
                    hp = ch.head_pos(tt)
                    for dx, dy in ((0, 0), (0.8 * k, 0), (-0.8 * k, 0), (0, 0.8 * k), (0, -0.8 * k)):
                        pr = _proj(p, q, th, hp + Vector((dx, dy, 1.9 * k)))
                        if pr:
                            worst = max(worst, pr[1])
                if worst <= 0.9:
                    break
                sp["tgt"] = sp["tgt"] + Z * 0.12 * k
        print(f"[cam] {s['name']}: {cam}/{sp['angle']} roll={sp['roll']:.0f} punch={sp['punch']} push={sp['push']:.2f}")


def _hidden(ob):
    return ob.hide_render or getattr(ob, "original", ob).hide_render


def _first_hit(dg, a, b, skip, frac=1.0, floor_z=None):
    """First hit on the segment a->b (within frac of its length) whose object is not in skip and is rendered
    (and, with floor_z=(lo, hi), is not floor / ceiling: a flat face below lo or above hi).
    Returns (distance, object name) or None."""
    d = b - a
    L = d.length * frac
    if L < 1e-3:
        return None
    d.normalize()
    o, gone = a.copy(), 0.0
    for _ in range(24):
        ok, loc, nrm, _, ob, _ = SC.ray_cast(dg, o, d, distance=L - gone)
        if not ok:
            return None
        gone = (loc - a).length
        floor = floor_z is not None and abs(nrm.z) > 0.85 and not floor_z[0] < loc.z < floor_z[1]
        if ob is not None and ob.name not in skip and not floor and not _hidden(ob):
            return gone, ob.name
        o = loc + d * 0.01
        gone += 0.01
        if gone >= L:
            return None
    return None


def deocclude(C, specs):
    """Ray-check every character shot at mid-shot: nothing but the subject may sit in the first 70% of the way
    to its head / chest, and the camera may not be inside or behind a wall. Rotate / raise until clear."""
    bpy = core.bpy
    names = {c.name: {c.root.name} | {o.name for o in c.root.children_recursive} for c in Char.ALL}
    all_char = set().union(*names.values()) if names else set()
    for i, (s, sp) in enumerate(zip(SHOTS, specs)):
        subj = sp.get("subj") or []
        t = sp["t_ref"]
        if not subj or any(c.head_pos(t).z < -100 for c in subj):
            continue
        SC.frame_set(frame(t))
        dg = bpy.context.evaluated_depsgraph_get()
        mine = set().union(*(names[c.name] for c in subj))
        pts = [c.head_pos(t) for c in subj] + [chest(c, t) for c in subj]
        anchor = sum((c.head_pos(t) for c in subj), Vector()) / len(subj)
        pivot = sum((c.base(t)[0] for c in subj), Vector()) / len(subj)
        front = facing(subj[0].base(t)[1])

        def variant(rot, lift):
            v = dict(sp)
            q = Quaternion((0, 0, 1), radians(rot))
            v["pos"] = pivot + q @ (sp["pos"] - pivot)
            v["tgt"] = pivot + q @ (sp["tgt"] - pivot)
            if lift:
                hd = Vector((v["pos"].x - anchor.x, v["pos"].y - anchor.y, 0)).length
                v["pos"] = v["pos"] + Vector((0, 0, lift * hd))
            # wall: from the subject back to the camera, nothing solid (non-character) may come first
            hit = _first_hit(dg, anchor, v["pos"], all_char)
            if hit:
                L = (v["pos"] - anchor).length
                if hit[0] - 0.4 < 0.55 * L:
                    return None, f"wall {hit[1]}"
                v["pos"] = anchor + (v["pos"] - anchor).normalized() * (hit[0] - 0.4)
            return v, None

        def blocked(v):
            p, q, fov = cam_pose(s, v, t)
            out = []
            for n_, x in enumerate(pts):   # heads: no other character before 92% of the way; else 70%
                hit = _first_hit(dg, p, x, mine, 0.92 if n_ < len(subj) else 0.7)
                if hit and (hit[0] < 0.7 * (x - p).length or hit[1] in all_char):
                    out.append(hit)
            # foreground clutter: a blob (hair, desk, shoulder) filling the frame near the lens, even off the
            # subject's line of sight. Sample a 6x10 grid: >10% of it within 40% of the way, or >20% within 60%.
            far = 0.6 * (anchor - p).length
            th = math.tan(radians(fov) / 2)
            hits = []
            for gx in range(6):
                for gy in range(10):
                    r = q @ Vector(((gx - 2.5) / 3 * th * 9 / 16, (gy - 4.5) / 5 * th, -1)).normalized()
                    hit = _first_hit(dg, p, p + r * far, mine, 1.0, floor_z=(pivot.z + 0.4, p.z + 1.0))
                    if hit:
                        hits.append(hit)
            close_ = [x for x in hits if x[0] < far * 2 / 3]
            if len(close_) > 6 or len(hits) > 12:
                out.append((min(x[0] for x in hits), "clutter:" + "+".join(sorted({x[1] for x in hits}))[:60]))
            return out

        tries = [(0, 0)]
        for a in (20, 40):
            pair = sorted((a, -a), key=lambda r: -(Quaternion((0, 0, 1), radians(r)) @ (sp["pos"] - pivot)).normalized().dot(front))
            tries += [(r, 0) for r in pair]
        tries += [(0, 0.45), (20, 0.45), (-20, 0.45), (0, 0.9), (60, 0), (-60, 0)]
        best, why0 = None, None
        for n, (rot, lift) in enumerate(tries):
            v, why = variant(rot, lift)
            if v is None:
                why0 = why0 or why
                continue
            if len(subj) == 1 and (rot or lift):
                off = Vector((v["pos"].x - pivot.x, v["pos"].y - pivot.y, 0))
                if off.length > 1e-3 and off.normalized().dot(front) < 0.15:
                    continue              # never swing round to the back of the head
            b = blocked(v)
            if best is None or len(b) < len(best[1]):
                best = (v, b, rot, lift, n)
            if not b:
                break
        if best is None:
            print(f"[cam] {s['name']}: no clear position ({why0})")
            continue
        v, b, rot, lift, n = best
        if b:                              # last resort: move in past the nearest blocker
            p = cam_pose(s, v, t)[0]
            dmin = min(x[0] for x in b)
            L = (anchor - p).length
            if dmin + 0.6 < 0.6 * L:
                w = dict(v)
                w["pos"] = v["pos"] + (v["tgt"] - v["pos"]).normalized() * (dmin + 0.6)
                if not blocked(w):
                    v, b = w, []
                    rot = f"{rot}+in"
        orig_b = blocked(sp) if n else b
        if n or v["pos"] != sp["pos"]:
            print(f"[cam] {s['name']}: {'blocked by ' + ','.join(sorted({x[1] for x in orig_b})) if orig_b else 'wall/back'}"
                  f" -> rot {rot} lift {lift}{' STILL ' + ','.join(sorted({x[1] for x in b})) if b else ' clear'}")
        sp["pos"], sp["tgt"] = v["pos"], v["tgt"]
        sp["push"] = v["push"]


def fg_frame(C, specs, most=3):
    """Real look: a few centred eye-level med / close singles get foreground framing - the camera swung / eased
    back until a desk edge, a prop or another person sits in the near foreground at one side or along the bottom
    (8-22% of the frame, soft from the depth of field) while the subject's head and chest stay clear."""
    bpy = core.bpy
    names = {c.name: {c.root.name} | {o.name for o in c.root.children_recursive} for c in Char.ALL}
    all_char = set().union(*names.values()) if names else set()
    last, n = -9, 0
    for i, (s, sp) in enumerate(zip(SHOTS, specs)):
        subj = sp.get("subj") or []
        if len(subj) != 1 or sp.get("post"):
            continue
        if not sp.get("want_fg"):          # fg:who always tries; otherwise a few spaced eye-level singles
            if n >= most or i - last < 4 or i in (0, len(SHOTS) - 1) or s["beat"] == "ME":
                continue
            if sp.get("preset") not in ("med", "close") or sp.get("angle") != "eye":
                continue
        ch, t = subj[0], sp["t_ref"]
        if ch.head_pos(t).z < -100:
            continue
        SC.frame_set(frame(t))
        dg = bpy.context.evaluated_depsgraph_get()
        mine = names[ch.name]
        head, ch_ = ch.head_pos(t), chest(ch, t)
        pivot = ch.base(t)[0]
        front = facing(ch.base(t)[1])
        k = ch.scale * ch.size_at(t)
        best = None
        wide_ = sp.get("want_fg")
        for rot in (0, 15, -15, 30, -30, 45, -45) + ((60, -60, 75, -75) if wide_ else ()):
            for back_ in (1.0, 1.3) + ((1.6, 2.0) if wide_ else ()):
                for dz in (0.0, -0.12):
                    qz = Quaternion((0, 0, 1), radians(rot))
                    v = dict(sp)
                    v["tgt"] = pivot + qz @ (sp["tgt"] - pivot)
                    v["pos"] = v["tgt"] + (pivot + qz @ (sp["pos"] - pivot) - v["tgt"]) * back_
                    off = Vector((v["pos"].x - pivot.x, v["pos"].y - pivot.y, 0))
                    v["pos"] = v["pos"] + Z * dz * off.length
                    if v["pos"].z < pivot.z + 1.4 * k or off.length < 1e-3 or off.normalized().dot(front) < 0.2:
                        continue
                    if _first_hit(dg, head, v["pos"], all_char):
                        continue                                    # behind a wall
                    p, q, fov = cam_pose(s, v, t)
                    if _first_hit(dg, p, head, mine, 0.92) or _first_hit(dg, p, ch_, mine, 0.8):
                        continue
                    th = math.tan(radians(fov) / 2)
                    far = 0.55 * (head - p).length
                    cells = []
                    for gx in range(8):
                        for gy in range(14):
                            x, y = (gx + 0.5) / 4 - 1, (gy + 0.5) / 7 - 1
                            r = (q @ Vector((x * th * 9 / 16, y * th, -1))).normalized()
                            if _first_hit(dg, p, p + r * far, mine, 1.0, floor_z=(pivot.z + 0.4, p.z + 1.5)):
                                cells.append((x, y))
                    share = len(cells) / 112
                    if not 0.07 <= share <= 0.2:
                        continue
                    ph = _proj(p, q, th, head)
                    if ph is None or sum(1 for x, y in cells if abs(x - ph[0]) < 0.35 and y > -0.45) > 2:
                        continue                                    # crowds the subject: a blocker, not a frame
                    cx = sum(c_[0] for c_ in cells) / len(cells)
                    cy = sum(c_[1] for c_ in cells) / len(cells)
                    if abs(cx) < 0.4 and cy > -0.35:
                        continue                                    # in the middle of the frame: a blob
                    sc = 4 * abs(share - 0.13) + abs(rot) / 90 + 0.3 * (back_ != 1.0) + 0.2 * (dz != 0)
                    if best is None or sc < best[0]:
                        best = (sc, v, rot, back_, dz, share, cx, cy)
        if best is None:
            if wide_:
                print(f"[cam] {s['name']}: no foreground to frame with")
            continue
        sc, v, rot, back_, dz, share, cx, cy = best
        sp["pos"], sp["tgt"], sp["fg"] = v["pos"], v["tgt"], True
        last, n = i, n + 1
        print(f"[cam] {s['name']}: foreground framing rot {rot} back {back_} dz {dz} fg {share:.2f}"
              f" at ({cx:.2f},{cy:.2f})")


def _sky_share(dg, pos, q, th, nx=8, ny=14):
    """Share of the frame that is ceiling (down-facing surfaces above the lens) or open sky."""
    n = sky = 0
    for gy in range(ny):
        for gx in range(nx):
            r = (q @ Vector((((gx + 0.5) / nx * 2 - 1) * th * 9 / 16, ((gy + 0.5) / ny * 2 - 1) * th, -1))).normalized()
            n += 1
            o, gone, hit = pos.copy(), 0.0, None
            for _ in range(12):
                ok, loc, nrm, _, ob, _ = SC.ray_cast(dg, o, r, distance=400 - gone)
                if not ok:
                    break
                gone = (loc - pos).length
                if ob is not None and not _hidden(ob):
                    hit = (loc, nrm)
                    break
                o = loc + r * 0.01
            if hit is None:
                sky += r.z > -0.02
            elif hit[1].z < -0.6 and hit[0].z > pos.z + 0.3:
                sky += 1
    return sky / max(1, n)


def cap_sky(C, specs, most=0.14):
    """Real look: any shot looking up keeps the ceiling / sky under ~15% of the frame: the camera rises (and
    eases in, so the subject gets bigger) until it does, keeping its target."""
    bpy = core.bpy
    for i, (s, sp) in enumerate(zip(SHOTS, specs)):
        if sp.get("preset") == "slide":
            continue
        t = sp["t_ref"]
        p, q, fov = cam_pose(s, sp, t)
        fwd = q @ Vector((0, 0, -1))
        if fwd.z < math.sin(radians(-3)) and sp.get("angle") != "low":
            continue                              # level / looking down: the ceiling is a thin band at most
        SC.frame_set(frame(t))
        dg = bpy.context.evaluated_depsgraph_get()
        th = math.tan(radians(fov) / 2)
        sh0 = sh = _sky_share(dg, p, q, th)
        if sh <= most:
            continue
        subj = sp.get("subj") or []
        k = subj[0].scale * subj[0].size_at(t) if subj else 1.0
        n = 0
        while sh > most and n < 14:
            n += 1
            v = sp["tgt"] - sp["pos"]
            sp["pos"] = sp["pos"] + Z * 0.3 * k + v * 0.04
            p, q, fov = cam_pose(s, sp, t)
            if (q @ Vector((0, 0, -1))).z < math.sin(radians(-8)):
                break
            sh = _sky_share(dg, p, q, th)
        print(f"[cam] {s['name']}: ceiling/sky {sh0:.2f} -> {sh:.2f} (camera up {n * 0.3 * k:.1f})")


DOF_K = float(os.environ.get("MILO_DOFK", "12"))      # our people are ~6 units tall: f-numbers on a 1:K scale
DOF_STOP = {"insert": 2.0, "pov": 2.0, "top": 2.0, "close": 2.8, "ots": 2.8, "fg": 4.0}


def _focus_point(sp, s, C, tt):
    if sp.get("focus") is not None:
        ch = sp.get("focus_ch")
        return sp["focus"] + (ch.head_pos(tt) - ch.head_pos(sp["t_ref"]) if ch else Vector())
    post = sp.get("post")
    if post and post[0] == "ots":
        return C[post[2]].head_pos(tt)
    subj = sp.get("subj") or []
    if subj:
        return sum((c.head_pos(tt) for c in subj), Vector()) / len(subj)
    return None


def dof_keys(C, specs, camf):
    """Real look: shallow depth of field, focused per frame on the shot's subject - the prop on inserts / POV /
    top-downs (f/2), the head on close-ups and OTS (f/2.8, b's head), the head on foreground-framed mediums
    (f/4); other mediums / wides f/8 unscaled = sharp. Keys focus distance + f-stop on every frame."""
    cd = core.CAM.data
    if os.environ.get("MILO_LOOK") == "brick":      # user rule 2026-11-08: brick videos have no blur at all
        cd.dof.use_dof = False
        return
    cd.dof.use_dof = True
    dists, stops = [], []
    for f, (pos, q, fov, k) in enumerate(camf):
        s, sp = SHOTS[k], specs[k]
        kind = "fg" if sp.get("fg") else "close" if sp.get("single") else sp.get("preset", s["cam"])
        fp = _focus_point(sp, s, C, f / 30)
        fwd = q @ Vector((0, 0, -1))
        d = (fp - pos).dot(fwd) if fp is not None else (sp["tgt"] - sp["pos"]).length
        if BRICK and fp is not None and (sp.get("focus") is None or (sp.get("post") or ("",))[0] == "face"):
            ch_ = sp.get("focus_ch") or (sp.get("subj") or [None])[0]
            kk = ch_.scale if ch_ is not None else 1.0
            d -= BRICK_CFG["focus_front"] * kk       # macro: focus on the printed face, not the head's centre
        dists.append(max(0.2, d))
        if BRICK:            # a 4 cm toy shot up close: f-numbers on the toy's scale (wides a little deeper)
            stops.append(BRICK_CFG["stops"].get(kind, 8.0) / BRICK_CFG["dof_k"])
        else:
            stops.append(DOF_STOP[kind] / DOF_K if kind in DOF_STOP else 8.0)
    frames = list(range(len(camf)))
    keys(cd, "dof.focus_distance", -1, frames, dists)
    keys(cd, "dof.aperture_fstop", -1, frames, stops)
    print(f"[cam] depth of field keyed: {sum(1 for x in stops if x < 1)} shallow frames of {len(stops)}")


def project(cam, p):
    pos, q, fov, _ = cam
    d = p - pos
    z = d.dot(q @ Vector((0, 0, -1)))
    if z <= 0.05:
        return None
    th = math.tan(radians(fov) / 2)
    return d.dot(q @ Vector((1, 0, 0))) / (z * th * 1080 / 1920), d.dot(q @ Vector((0, 1, 0))) / (z * th)


def crowd_cutoffs(C, camf):
    hidden = {}
    for i, s in enumerate(SHOTS):
        f0, f1 = frame(s["t0"]), frame(s["t1"]) - 1
        for c in C["_crowd"]:
            for f in (f0, (f0 + f1) // 2, f1):
                top, feet = c.head_top(f / 30)
                pt, pf = project(camf[f], top + Vector((0, 0, 0.45))), project(camf[f], feet)
                if pt and pf and abs(pt[0]) < 1.05 and pt[1] > 1.0 and pf[1] < 1.0:
                    hidden.setdefault(c.name, set()).update(range(f0, f1 + 1))
                    break
                # a crowd member right at the lens (slides through a crowd) is a blob, not a character
                mid = (top + feet) / 2
                pm = project(camf[f], mid)
                if pm and abs(pm[0]) < 1.3 and (mid - camf[f][0]).length < 6.5 * c.scale:
                    hidden.setdefault(c.name, set()).update(range(f0, f1 + 1))
                    break
    return hidden


# ---------------------------------------------------------------- main
PLAN_BEATS = [None] * len(D.STAGE)
for s in SHOTS:
    PLAN_BEATS[s["line"]] = s["beat"]


def build():
    S = SETLIB.build(D.SETS)
    core.build_camera() if hasattr(core, "build_camera") else None
    cd = core.bpy.data.cameras.new("Cam")
    cd.sensor_fit, cd.sensor_height = "VERTICAL", 24.0
    cd.clip_start, cd.clip_end = 0.1, 1500
    cd.dof.use_dof = False
    core.CAM = core.bpy.data.objects.new("Cam", cd)
    core.COLL.objects.link(core.CAM)
    SC.camera = core.CAM
    build_props(S)
    C = make_cast(S)
    stage(C, S)
    specs = [cam_for(s, i, C, S) for i, s in enumerate(SHOTS)]
    real = REALCAM
    for i, (s, sp) in enumerate(zip(SHOTS, specs)):
        sp["t_ref"] = (s["t0"] + s["t1"]) / 2
    if real:
        # a 70 deg game-style lens + top-channel grammar: 3/4, low/high, thirds, Dutch, push, punch
        real_grammar(specs, C, S)
    camf = camera_frames(specs)
    hidden = crowd_cutoffs(C, camf)
    for c in Char.ALL:
        c.write_outfits()
        c.write_motion(hidden.get(c.name, set()))
    post = any(sp.get("post") for sp in specs)
    if post:
        # inserts + over-the-shoulders need the real hand / head positions of the posed scene
        post_cams(C, specs)
    if real:
        # ray-check every character shot against the posed scene; re-frame what is blocked
        deocclude(C, specs)
        fg_frame(C, specs)             # a desk edge / prop / person soft in the near foreground on a few mediums
        cap_sky(C, specs)              # low angles: the ceiling / sky under ~15% of the frame
    if real or post:
        camf = camera_frames(specs)
        h2 = crowd_cutoffs(C, camf)
        for c in Char.ALL:
            if h2.get(c.name, set()) != hidden.get(c.name, set()):
                c.write_motion(h2.get(c.name, set()))
        hidden = h2
    frames = list(range(NF))
    for i in range(3):
        keys(core.CAM, "location", i, frames, [d[0][i] for d in camf])
    eul = [d[1].to_euler() for d in camf]
    for i in range(3):
        keys(core.CAM, "rotation_euler", i, frames, [e[i] for e in eul])
    keys(core.CAM.data, "lens", -1, frames, [12.0 / math.tan(radians(d[2]) / 2) for d in camf])
    if real:
        dof_keys(C, specs, camf)
    build_heads()
    core.build_puffs()
    import look
    # channel look: cel + ink + Milo grade; brick also runs the stop-motion pass (on twos + jitter + flicker)
    look.apply(LOOK, C, SC, NF, shots=SHOTS)
    print(f"built {EP}: {len(Char.ALL)} characters, {len(core.PUFFS)} puffs, {NF} frames, "
          f"{len(hidden)} crowd lifted out")


def main():
    build()
    if MODE == "blend":
        core.bpy.ops.wm.save_as_mainfile(filepath=OUT)
    elif MODE == "stills":
        os.makedirs(OUT, exist_ok=True)
        SC.render.resolution_percentage = 50
        SC.eevee.taa_render_samples = 12
        only = set(ARGV[2].split(",")) if len(ARGV) > 2 and ARGV[2] else None
        for k, s in enumerate(SHOTS):
            if only and s["name"] not in only and str(k) not in only:
                continue
            SC.frame_set((frame(s["t0"]) + frame(s["t1"]) - 1) // 2)
            SC.render.filepath = os.path.join(OUT, s["name"] + ".png")
            core.bpy.ops.render.render(write_still=True)
    elif MODE == "frames":
        os.makedirs(OUT, exist_ok=True)
        SC.frame_start = int(ARGV[2]) if len(ARGV) > 2 else 0
        SC.frame_end = int(ARGV[3]) if len(ARGV) > 3 else NF - 1
        SC.render.filepath = os.path.join(OUT, "f_")
        if os.environ.get("MILO_PCT"):          # quick motion tests: smaller frames, fewer samples
            SC.render.resolution_percentage = int(os.environ["MILO_PCT"])
            SC.eevee.taa_render_samples = 12
        if BRICK:          # stop motion: render each held pose once, copy it onto the frames that hold it
            import shutil
            src = _look.hold_schedule(SHOTS, NF)
            for f in range(SC.frame_start, SC.frame_end + 1):
                dst = os.path.join(OUT, f"f_{f:04d}.png")
                s0 = max(int(src[f]), SC.frame_start)
                if s0 != f:
                    shutil.copyfile(os.path.join(OUT, f"f_{s0:04d}.png"), dst)
                    continue
                SC.frame_set(f)
                SC.render.filepath = dst
                core.bpy.ops.render.render(write_still=True)
            return
        core.bpy.ops.render.render(animation=True)


main()
