"""The episode direction language (pure Python, shared by plan.py and Blender's build.py).

An episode file (episodes/epNN.py) holds, besides its lines in season1.py:
    SETS  = ["home", "classroom", ...]            sets to build
    WHO   = ["milo", "dad", ...]                   cast in this episode
    CROWD = ("museum", "stone", 44)                crowd set, its form, and how many (or None)
    STAGE = [L(...), ...]                          one L() per script line, in order

L(set, who, cams="wide close", at="", do="")
    set   the set this line plays in
    who   the subject the camera frames by default
    cams  shots in this line, left to right: "wide close" makes two shots. A shot can name its cut word
          ("close@Statue", "close@$+0.6" = 0.6 s after the last word) and its subject ("close:kai").
          Presets: close, med, two:a,b, wide, wide:set, slide, low, high, plus
            insert:who        macro on the prop in who's hand (who must hold one: form hold_X), ~50 deg, slightly
                              high, the prop ~half the frame, the face soft behind it
            insert:who:face   extreme close-up of who's face
            pov:who           first person: from just behind / above who's head, looking down at the prop in
                              their hand(s) (lower half of the frame), the scene beyond; ~60 deg. Best with props
                              held low (pose holdout / phone / carry / hold); a mic at the mouth is skipped for
                              the prop in the other hand. Looks the way who faces.
            top:who           top-down insert (~75 deg down) on the prop in who's hand(s); no prop = who from above
            ots:a,b           over a's shoulder onto b (a's head + shoulder at one edge, b on the other third);
                              a and b should face each other (at "a@..>b b@..>a"). If a's head can't be in frame
                              it becomes a clean single on b.
            fg:who            a medium with foreground framing (desk edge / prop / person soft in front)
          Real look: never 3 eye-level close/med/two in a row; the 3rd becomes a prop shot (subject holds a prop:
          pov / top when held low, else insert), an OTS (someone faces the subject) or a low/high angle. Shallow
          depth of field on close / insert / pov / top / OTS (focus on the head or the prop).
    at    placements at the start of this line: "dad@home.center mom@home.couch>dad"
          (>name faces that character, :deg sets a heading)
    do    events keyed to words: "Clack> dad form stone; Statue> dad pose shock/shock"
          Word may be Word#2 (2nd in the line), ^ (line start) or $ (last word), plus +0.3 offsets.
          Actions: pose P[/face] | face F | form NAME [nopuff] | puff [size] | size K | lift DZ | run SPOT
                   | turn CHAR | show SPOT | hide | spin | flail S | swap CHAR | snapto CHAR [pose/face]
                   | sfx NAME [dB]
                   | pop SPOT [dx dy dz]... [face] | pop up | pop scatter | pile SPOT [dx dy dz] CHAR... [face]
          who "crowd" means every crowd member; "all" means everyone in that set.
"""
import re


def L(set, who, cams="wide", at="", do=""):
    return dict(set=set, who=who, cams=cams.split(), at=at.split(), do=[e.strip() for e in do.split(";") if e.strip()])


def parse_event(s):
    """'Clack#2+0.1> dad form stone' -> dict(word, nth, off, who, act, args)."""
    m = re.match(r"^\s*([^>]+?)\s*>\s*(\S+)\s+(\S+)\s*(.*)$", s)
    if not m:
        raise ValueError(f"bad event: {s}")
    ref, who, act, rest = m.groups()
    word, nth, off = parse_ref(ref)
    return dict(word=word, nth=nth, off=off, who=who, act=act, args=rest.split())


def parse_ref(ref):
    m = re.match(r"^([^#+\-]+|\^|\$)(?:#(\d+))?([+\-][\d.]+)?$", ref.strip())
    if not m:
        raise ValueError(f"bad word ref: {ref}")
    word, nth, off = m.groups()
    return word, int(nth or 1) - 1, float(off or 0)


def parse_cam(s):
    """'close:kai@Statue+0.2' -> (preset, subject or None, cutref or None)."""
    cut = None
    if "@" in s:
        s, cut = s.split("@", 1)
    preset, _, subj = s.partition(":")
    return preset, subj or None, cut


def parse_at(s):
    """'mom@home.couch>dad' / 'dad@home.center:180' -> (who, set, spot, face_char, heading)."""
    who, _, where = s.partition("@")
    face, hd = None, None
    if ">" in where:
        where, face = where.split(">", 1)
    if ":" in where:
        where, hd = where.split(":", 1)
        hd = float(hd)
    st, _, spot = where.partition(".")
    return who, st, spot, face, hd


def word_time(words, line, word, nth=0, off=0.0):
    """Time of a word in a script line (0-based line). ^ = first word, $ = last word."""
    ws = [w for w in words if w["line"] == line]
    if word == "^":
        w = ws[0]
    elif word == "$":
        w = ws[-1]
    else:
        hits = [w for w in ws if w["text"].lower() == word.lower()]
        if len(hits) <= nth:
            raise KeyError(f"line {line + 1}: no word '{word}' #{nth + 1} in: {' '.join(x['text'] for x in ws)}")
        w = hits[nth]
    return w["start"] + off
