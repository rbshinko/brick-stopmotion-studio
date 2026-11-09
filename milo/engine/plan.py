"""Plan an episode from its direction + word timings: shots, sound effects and music gaps.
python engine/plan.py   (MILO_EP=epNN)  ->  work/epNN/plan.json"""
import importlib, json, os, re, statistics, sys
from epdata import EP, WORK, BEATS, load_words, EPISODES
from dsl import parse_cam, parse_event, parse_ref, word_time

CUT_LEAD, HOLD_END = 0.04, 1.5
MIN_SHOT, MAX_SHOT = 0.6, 2.5

# sound words said out loud -> (sound, dB); pops also get a sparkle
SOUND_WORDS = {
    "pop": ("pop", -17), "poof": ("pop", -17), "clack": ("impact", -19), "clunk": ("impact", -19),
    "crack": ("crack", -16), "snip": ("snip", -16), "zip": ("zip", -21), "swoosh": ("whoosh", -21),
    "whoosh": ("whoosh", -21), "boing": ("boing", -16), "thwack": ("slap", -19), "ding": ("ding", -16),
    "tweet": ("whistle", -16), "bawk": ("chicken", -16), "wrap": ("whoosh", -22), "ha": ("laugh", -16),
    "yawn": ("whoosh", -24), "flash": ("ding", -16),
}
# the one sound that lands in the music gap, by the QUIET line's key noun
QUIET_CUES = {"giggle": "laugh", "knock": "knock", "doorbell": "doorbell", "squeak": "squeak",
              "cough": "cough", "snore": "bubbles", "growled": "growl", "music": "ding", "mine": "dizzy"}


def stage():
    sys.path.insert(0, os.path.join(os.path.dirname(WORK), "..", "episodes"))
    return importlib.import_module(EP)


def main():
    words = load_words()
    D = stage()
    lines = D.STAGE
    assert len(lines) == len(BEATS), f"{EP}: {len(lines)} STAGE entries for {len(BEATS)} lines"
    end = words[-1]["end"] + HOLD_END

    # ---- shots: each line's cams split it at their cut words (or evenly by words)
    shots = []
    for li, st in enumerate(lines):
        ws = [w for w in words if w["line"] == li]
        cams = [parse_cam(c) for c in st["cams"]]
        starts = []
        for k, (preset, subj, cut) in enumerate(cams):
            if k == 0:
                t = ws[0]["start"] - CUT_LEAD
            elif cut:
                w, n, off = parse_ref(cut)
                t = word_time(words, li, w, n, off) - (CUT_LEAD if off == 0 else 0)
            else:
                t = ws[round(len(ws) * k / len(cams))]["start"] - CUT_LEAD
            starts.append((t, preset, subj or st["who"]))
        for t, preset, subj in starts:
            shots.append(dict(t0=max(0.0, t) if shots else 0.0, cam=preset, who=subj, set=st["set"], line=li,
                              beat=BEATS[li]))
    for i, s in enumerate(shots):
        s["t1"] = shots[i + 1]["t0"] if i + 1 < len(shots) else end
        s["name"] = f"{i:02d}_{s['beat'].lower()}_{s['cam']}"

    # ---- sound effects
    sfx = []
    def add(t, name, db):
        if not any(abs(t - e[0]) < 0.15 and e[1] == name for e in sfx):
            sfx.append((round(t, 3), name, db))
    pop_n = 0
    for w in words:
        k = re.sub(r"[^a-z]", "", w["text"].lower())
        if k in SOUND_WORDS:
            name, db = SOUND_WORDS[k]
            if name == "pop":
                name, pop_n = ("pop1", "pop2")[pop_n % 2], pop_n + 1
                add(w["start"], "sparkle", -24)
            add(w["start"], name, db)
    for li, st in enumerate(lines):
        for e in map(parse_event, st["do"]):
            t = word_time(words, li, e["word"], e["nth"], e["off"])
            if e["act"] == "form" and "nopuff" not in e["args"]:
                add(t, "pop1", -17); add(t, "sparkle", -24)
            elif e["act"] in ("puff", "show", "pile") or (e["act"] == "pop" and e["who"] != "crowd"):
                add(t, "pop2", -17); add(t, "sparkle", -24)
            elif e["act"] == "sfx":
                add(t, e["args"][0], float(e["args"][1]) if len(e["args"]) > 1 else -16)
            elif e["act"] == "snapto":
                add(t, "whoosh", -21)
        keyw = [w for w in words if w["line"] == li and w["key"]]
        if BEATS[li] == "VICTIM" and keyw:
            add(keyw[-1]["start"], "gasp", -22)
        if BEATS[li] == "ME" and keyw:
            add(keyw[-1]["start"], "impact", -19); add(keyw[-1]["start"], "sparkle", -24)
        if BEATS[li] == "QUIET" and keyw:
            cue = QUIET_CUES.get(keyw[-1]["text"].lower().strip("'s"))
            if cue:
                add(keyw[-1]["start"], cue, -16)
        if BEATS[li] == "REVEAL":
            add(next(s["t0"] for s in shots if s["line"] == li), "whoosh2", -25)
    for a, b in zip(shots, shots[1:]):
        if a["set"] != b["set"] and b["beat"] != "REVEAL":
            add(b["t0"], "whoosh2", -25)
    add(words[-1]["start"], "sting", -17)
    sfx.sort()

    # ---- music: out for the QUIET beat until the twist's first word, and again from the final snap
    quiet = BEATS.index("QUIET")
    twist = BEATS.index("TWIST")
    q0 = [w for w in words if w["line"] == quiet][0]["start"] - 0.06
    t1 = [w for w in words if w["line"] == twist][0]["start"]
    snap = None
    for li, st in enumerate(lines):
        for e in map(parse_event, st["do"]):
            if e["act"] == "snapto":
                snap = word_time(words, li, e["word"], e["nth"], e["off"])
    final = (snap if snap else words[-1]["start"]) - 0.06
    gaps = [(q0, t1), (final, None)]

    # ---- checks
    durs = [round((s["t1"] - s["t0"]) * 30) / 30 for s in shots]
    bad = [(s["name"], d) for s, d in zip(shots, durs) if not MIN_SHOT - 0.02 <= d <= MAX_SHOT]
    plan = dict(ep=EP, title=EPISODES[EP]["title"], end=end, shots=shots, sfx=sfx, music_gaps=gaps,
                music=getattr(D, "MUSIC", "island"))
    with open(os.path.join(WORK, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    print(f"{EP}: {len(shots)} shots, {end:.1f} s, median {statistics.median(durs):.2f} s, "
          f"{len(shots) / end * 30:.1f} per 30 s, {len(sfx)} sfx")
    if bad:
        print("SHOT LENGTH PROBLEMS:", bad)
        sys.exit(2)


if __name__ == "__main__":
    main()
