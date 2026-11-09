"""Episode text for the pure-Python stages (voice, align, plan, post). MILO_EP picks the episode."""
import json, os, re, sys

ENGINE = os.path.dirname(os.path.abspath(__file__))
MILO = os.path.dirname(ENGINE)
sys.path.insert(0, os.path.join(MILO, "episodes"))
from season1 import EPISODES

EP = os.environ.get("MILO_EP", "ep01")
WORK = os.path.join(MILO, "work", EP)
os.makedirs(WORK, exist_ok=True)
BEATS = [b for b, _ in EPISODES[EP]["lines"]]
LINES = [{"text": t} for _, t in EPISODES[EP]["lines"]]
# pause after each line: 0.06 s base plus 0.04-0.14 s, and the longest (0.24) right before the twist
GAP_EXTRA = [0.24 if i + 1 < len(BEATS) and BEATS[i + 1] == "TWIST" else (0.04, 0.08, 0.06, 0.12, 0.10)[i % 5]
             for i in range(len(BEATS))]
GAP_EXTRA[-1] = 0.0


def tts_text(line):
    return line.get("tts", line["text"].replace("[", "").replace("]", ""))


def words():
    out = []
    for li, line in enumerate(LINES):
        key = False
        for raw in line["text"].split():
            if "[" in raw:
                key = True
            w = re.sub(r"[^A-Za-z0-9']", "", raw.replace("[", "").replace("]", ""))
            if w:
                out.append({"text": w[0].upper() + w[1:], "key": key, "line": li})
            if "]" in raw:
                key = False
    return out


def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def load_words():
    with open(os.path.join(WORK, "words.json")) as f:
        return json.load(f)["words"]
