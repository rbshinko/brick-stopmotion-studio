"""Judge board (run from milo/engine): every 5th shot of an episode (from 2) with its real caption, over 6 reference frames.
usage (from milo/engine, MILO_EP + MILO_LOOK=real set): python epboard.py OUT.jpg"""
import sys, json, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))
from PIL import Image, ImageDraw
import post
from epdata import load_words, EP
plan = json.load(open(f"../work/{EP}/plan.json", encoding="utf-8"))
words = load_words(); groups = post.chunk_words(words)
pick = [s for s in plan["shots"] if int(s["name"][:2]) % 5 == 2][:6]
W, H = 300, 533
refs = ["r02/s05", "r03/s10", "r05/s08", "r06/s15", "r10/s20", "r08/s10"]
im = Image.new("RGB", (W * 6, H * 2 + 40), "white"); d = ImageDraw.Draw(im)
for i, s in enumerate(pick):
    tm = (s["t0"] + s["t1"]) / 2
    gi = max((k for k, g in enumerate(groups) if words[g[0]]["start"] <= tm), default=0)
    text, key = post.chunk_text(words, groups[gi])
    f = Image.open(f"../work/{EP}/stills/{s['name']}.png").convert("RGBA").resize((1080, 1920))
    f.alpha_composite(post.caption_layer_real(text, key))
    im.paste(f.convert("RGB").resize((W, H)), (i * W, 20))
for i, r in enumerate(refs):
    im.paste(Image.open(f"../reference/" + os.environ.get("MILO_REF", "ref") + "/frames/{r}.jpg").convert("RGB").resize((W, H)), (i * W, H + 40))
d.text((4, 4), "OURS (top)", fill="black"); d.text((4, H + 24), "REFERENCE (bottom)", fill="black")
im.save(sys.argv[1], quality=90)
print([s["name"] for s in pick])
