"""After the render: flag frames where nothing moves, and lay every 3rd frame out on contact sheets."""
import os
import numpy as np
from PIL import Image, ImageDraw
import json
from epdata import WORK

FR = os.path.join(WORK, "frames")
DST = os.path.join(WORK, "check")
TW, TH, COLS, ROWS = 90, 160, 12, 4


def main():
    os.makedirs(DST, exist_ok=True)
    plan = json.load(open(os.path.join(WORK, "plan.json"), encoding="utf-8"))
    fr = lambda t: int(round(t * 30))
    nf = fr(plan["end"])
    cuts = {fr(s["t0"]) for s in plan["shots"]}
    shot_of = {}
    for s in plan["shots"]:
        for f in range(fr(s["t0"]), fr(s["t1"])):
            shot_of[f] = s["name"]
    missing = [f for f in range(nf) if not os.path.exists(os.path.join(FR, f"f_{f:04d}.png"))]
    if missing:
        print("missing frames:", missing[:20], "..." if len(missing) > 20 else "")
    prev, still, flat = None, [], []
    thumbs = []
    for f in range(nf):
        p = os.path.join(FR, f"f_{f:04d}.png")
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        small = np.asarray(im.resize((270, 480)), np.int16)
        if prev is not None and f not in cuts and np.abs(small - prev).max() == 0:
            still.append((f, shot_of.get(f)))
        prev = small
        if f % 3 == 0:
            thumbs.append((f, im.resize((TW, TH))))
            if small.std() < 14:          # nearly one flat colour: camera in a wall, only sky, hidden subject
                flat.append((f, shot_of.get(f)))
    print(f"{nf - len(missing)} frames, {len(still)} frames identical to the one before:", still[:30])
    shots_flat = sorted({n for _, n in flat})
    print(f"{len(flat)} of every-3rd frames look flat/empty" + (f" in shots: {shots_flat}" if flat else ""))
    per = COLS * ROWS
    for s in range(0, len(thumbs), per):
        sheet = Image.new("RGB", (COLS * TW, ROWS * (TH + 12)), "white")
        d = ImageDraw.Draw(sheet)
        for i, (f, t) in enumerate(thumbs[s:s + per]):
            x, y = (i % COLS) * TW, (i // COLS) * (TH + 12)
            sheet.paste(t, (x, y))
            d.text((x + 2, y + TH), str(f), fill="red" if f in cuts else "black")
        sheet.save(os.path.join(DST, f"sheet{s // per:02d}.png"))
    print("sheets:", (len(thumbs) + per - 1) // per)


if __name__ == "__main__":
    main()
