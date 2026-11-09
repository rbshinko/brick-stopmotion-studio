"""CC0 surface textures from Poly Haven (polyhaven.com, CC0: no credit needed), cached in assets/textures/<id>/.
   python engine/textures.py          -> downloads every texture in TEX (1k jpg: colour, normal, roughness)"""
import json, os, urllib.request

MILO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(MILO, "assets", "textures")
UA = {"User-Agent": "milo-engine/1.0"}

# role -> Poly Haven id, tiling (texture repeats per 4 m)
TEX = {
    "marble":  ("marble_01", 1.0),
    "terrazzo": ("terrazzo_tiles", 1.0),
    "carpet":  ("dirty_carpet", 1.5),
    "wood":    ("laminate_floor", 1.0),
    "planks":  ("brown_planks_05", 1.0),
    "cobble":  ("cobblestone_floor_001", 1.0),
    "brick":   ("brick_4", 1.0),
    "asphalt": ("asphalt_02", 0.5),
    "grass":   ("leafy_grass", 0.5),
    "tiles":   ("large_floor_tiles_02", 1.0),
    "denim":   ("denim_fabric", 4.0),
    "plaster": ("painted_plaster_wall", 0.5),
}
MAPS = {"Diffuse": "diff", "nor_gl": "nor", "Rough": "rough"}


def paths(role):
    pid = TEX[role][0]
    return {k: os.path.join(DIR, pid, f"{k}.jpg") for k in MAPS.values()}


def fetch(pid):
    os.makedirs(os.path.join(DIR, pid), exist_ok=True)
    files = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.polyhaven.com/files/{pid}", headers=UA)))
    for key, short in MAPS.items():
        dst = os.path.join(DIR, pid, f"{short}.jpg")
        if os.path.exists(dst):
            continue
        url = files[key]["1k"]["jpg"]["url"]
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r, open(dst, "wb") as f:
            f.write(r.read())
    print("ok", pid)


if __name__ == "__main__":
    for role, (pid, _) in TEX.items():
        fetch(pid)
