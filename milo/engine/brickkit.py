"""Toy-brick set kit (runs inside Blender; only used when MILO_LOOK=brick).

Scale (engine units; a ~5.2-unit character = a ~4-brick-tall figure, so 1 unit = 8 mm):
    stud pitch U = 1.0, plate = 0.4, brick = 1.2, stud = 0.6 wide x 0.2 tall. Sets are built so that
    their walking surfaces (baseplates, floors) have their top at z = 0, like the other looks.

How it is built
- Pieces are real geometry with a small chamfer on every edge (CH), so seams between bricks/tiles are real
  V-grooves that catch light: walls are running-bond courses, floors are plates or tiles, roofs are stacked
  slope bricks, trees are round bricks + leaf plates. One mesh object per colour, built with bmesh.
- Studs on big flat tops (baseplates, floors, furniture, wall tops) are a Geometry Nodes modifier
  ("BrickStuds") that instances one stud on a 1-unit grid over the object's top face. The instances use the
  object's own material slot and Object Info colour, so they always match the piece. The modifier is
  render-only (show_viewport = False), so build.py's camera ray casts never see (or pay for) studs.
  Small pieces (trees, round bricks, roof ridges) get a few real-geometry studs instead.

Contract for the look agent (materials) - every set object made in brick mode carries ob["brick"]:
    "base"      baseplate (studded, matte-ish plastic)
    "plate"     plate / brick with studs on top (furniture, floors, sidewalks)
    "tile"      smooth tile top, no studs (table tops, counters, road, polished floors)
    "wall"      running-bond brick wall; seams are real geometry (no seam shader needed).
                ob["brickwall"] = True as well.
    "slope"     sloped roof bricks (could take a slightly rougher, grainy top)
    "round"     round bricks / leaf pieces (trees, bushes, plants, silo)
    "glass"     transparent pane (windows, door lites). Fallback material "BrickGlass" (alpha); restyle it as
                trans-clear plastic if you like.
    "print"     printed/flat decoration (backdrop clouds)
    "backdrop"  printed sky card behind outdoor sets / outside windows; fallback material "BrickSkyCard"
                (emissive gradient). Keep it out of focus with the macro DOF.
    "table"     the real-world wooden tabletop the sets stand on (object "ground", also ob["tex"]="wood",
                so look.tex_material("wood") gives it photo wood).
Objects with no ob["brick"] are the old bevelled set-dressing boxes (setkit), which are already toy-plastic.
Please do NOT run look.texture_world()'s name rules in brick mode (they would put photo floors / plaster on
bricks); only ob["tex"] (the tabletop) should get a texture. There is no ceiling ("_ceil") in brick mode: sets
are open-topped like a tabletop set, lit from above. Rooms get their own one-sided front wall
"<set>_front" (backface-culled, material "BrickFront"), so reverse angles see a brick wall, not the table.
"""
import os
from math import cos, sin, pi, floor, sqrt, radians
import bmesh
import bpy
from mathutils import Vector
import core
from core import lin

BRICK = os.environ.get("MILO_LOOK") == "brick"
U, PLATE, BRICK_H = 1.0, 0.4, 1.2
STUD_R, STUD_H = 0.3, 0.2
CH = 0.05                 # chamfer on piece edges: this is what draws the seams
BASE_TOP_IN = -0.2        # indoor baseplate top (the floor plate sits on it, top at z 0)
TABLE_Z = -0.4            # top of the real-world tabletop


# ---------------------------------------------------------------- bmesh pieces
def block(bm, x0, x1, y0, y1, z0, z1, c=CH):
    """Chamfered box (24 verts, 26 faces) from corner to corner."""
    if x1 < x0: x0, x1 = x1, x0
    if y1 < y0: y0, y1 = y1, y0
    if z1 < z0: z0, z1 = z1, z0
    hx, hy, hz = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
    cx, cy, cz = x0 + hx, y0 + hy, z0 + hz
    c = max(0.002, min(c, 0.35 * min(hx, hy, hz) * 2))
    V = {}
    for a in (-1, 1):
        for b in (-1, 1):
            for g in (-1, 1):
                V[a, b, g, 0] = bm.verts.new((cx + a * hx, cy + b * (hy - c), cz + g * (hz - c)))
                V[a, b, g, 1] = bm.verts.new((cx + a * (hx - c), cy + b * hy, cz + g * (hz - c)))
                V[a, b, g, 2] = bm.verts.new((cx + a * (hx - c), cy + b * (hy - c), cz + g * hz))
    F = bm.faces.new
    sq = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    out = []
    for s in (-1, 1):
        out.append(F([V[s, p, q, 0] for p, q in sq]))
        out.append(F([V[p, s, q, 1] for p, q in sq]))
        out.append(F([V[p, q, s, 2] for p, q in sq]))
    for p in (-1, 1):
        for q in (-1, 1):
            out.append(F([V[-1, p, q, 1], V[1, p, q, 1], V[1, p, q, 2], V[-1, p, q, 2]]))
            out.append(F([V[p, -1, q, 0], V[p, 1, q, 0], V[p, 1, q, 2], V[p, -1, q, 2]]))
            out.append(F([V[p, q, -1, 0], V[p, q, 1, 0], V[p, q, 1, 1], V[p, q, -1, 1]]))
    for a in (-1, 1):
        for b in (-1, 1):
            for g in (-1, 1):
                out.append(F([V[a, b, g, 0], V[a, b, g, 1], V[a, b, g, 2]]))
    _orient(out, Vector((cx, cy, cz)))
    return out


def _orient(faces, centre):
    """Convex piece: every face normal points away from its centre."""
    for f in faces:
        f.normal_update()
        if f.normal.dot(f.calc_center_median() - centre) < 0:
            f.normal_flip()


def cyl(bm, cx, cy, z0, z1, r, seg=20, c=CH, smooth=True):
    """Chamfered upright cylinder (round brick / plate)."""
    c = min(c, 0.3 * (z1 - z0), 0.3 * r)
    rings = []
    for rr, z in ((r - c, z0), (r, z0 + c), (r, z1 - c), (r - c, z1)):
        rings.append([bm.verts.new((cx + rr * cos(2 * pi * i / seg), cy + rr * sin(2 * pi * i / seg), z))
                      for i in range(seg)])
    out = []
    for k in range(3):
        A, B = rings[k], rings[k + 1]
        for i in range(seg):
            j = (i + 1) % seg
            f = bm.faces.new((A[i], A[j], B[j], B[i]))
            f.smooth = smooth
            out.append(f)
    out.append(bm.faces.new(rings[0]))
    out.append(bm.faces.new(rings[3]))
    _orient(out, Vector((cx, cy, (z0 + z1) / 2)))
    return out


def stud(bm, x, y, z, r=STUD_R, h=STUD_H):
    cyl(bm, x, y, z, z + h, r, seg=14, c=0.035)


def wedge(bm, x0, x1, poly):
    """Prism along X from a convex YZ polygon [(y, z), ...] (slope bricks)."""
    vs0 = [bm.verts.new((x0, y, z)) for y, z in poly]
    vs1 = [bm.verts.new((x1, y, z)) for y, z in poly]
    out = [bm.faces.new(vs0), bm.faces.new(vs1)]
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        out.append(bm.faces.new((vs0[i], vs0[j], vs1[j], vs1[i])))
    cy = sum(p[0] for p in poly) / n
    cz = sum(p[1] for p in poly) / n
    _orient(out, Vector(((x0 + x1) / 2, cy, cz)))


def obj(name, bm, loc, col, kind, rz=0.0, shadow=True):
    """bmesh -> mesh object (Plain material, object colour), flagged ob['brick'] = kind."""
    me = core.finish(bm, name)
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=radians(50))
    ob = bpy.data.objects.new(name, me)
    core.COLL.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (0, 0, radians(rz))
    ob.color = lin(col) if isinstance(col, str) else col
    ob["brick"] = kind
    if kind == "wall":
        ob["brickwall"] = True
    if not shadow:
        ob.visible_shadow = False
    return ob


# ---------------------------------------------------------------- studs (Geometry Nodes)
_GN = {}


def _stud_group():
    if "g" in _GN:
        return _GN["g"]
    g = bpy.data.node_groups.new("BrickStuds", "GeometryNodeTree")
    I = g.interface
    I.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for nm, kind in (("Count X", "NodeSocketInt"), ("Count Y", "NodeSocketInt"), ("Size", "NodeSocketVector"),
                     ("Centre", "NodeSocketVector"), ("Inv Scale", "NodeSocketVector")):
        I.new_socket(nm, in_out="INPUT", socket_type=kind)
    I.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = g.nodes.new, g.links.new
    gi, go = N("NodeGroupInput"), N("NodeGroupOutput")
    sep = N("ShaderNodeSeparateXYZ")
    L(gi.outputs["Size"], sep.inputs[0])
    grid = N("GeometryNodeMeshGrid")
    L(sep.outputs["X"], grid.inputs["Size X"]); L(sep.outputs["Y"], grid.inputs["Size Y"])
    L(gi.outputs["Count X"], grid.inputs["Vertices X"]); L(gi.outputs["Count Y"], grid.inputs["Vertices Y"])
    mv = N("GeometryNodeTransform")
    L(grid.outputs["Mesh"], mv.inputs["Geometry"]); L(gi.outputs["Centre"], mv.inputs["Translation"])
    # one stud, bottom at z 0: smooth side + a small chamfer ring on top (the rim highlight)
    parts = []
    for kind, z, depth, r0, r1 in (("cyl", 0.0, STUD_H - 0.035, STUD_R, STUD_R), ("cone", STUD_H - 0.035, 0.035,
                                                                                 STUD_R, STUD_R - 0.045)):
        if kind == "cyl":
            m = N("GeometryNodeMeshCylinder")
            m.inputs["Radius"].default_value = r0
        else:
            m = N("GeometryNodeMeshCone")
            m.inputs["Radius Bottom"].default_value = r0
            m.inputs["Radius Top"].default_value = r1
        m.inputs["Vertices"].default_value = 16
        m.inputs["Depth"].default_value = depth
        sm = N("GeometryNodeSetShadeSmooth")
        L(m.outputs["Mesh"], sm.inputs["Geometry"]); L(m.outputs["Side"], sm.inputs["Selection"])
        t = N("GeometryNodeTransform")
        t.inputs["Translation"].default_value = (0, 0, z + depth / 2)
        L(sm.outputs["Geometry"], t.inputs["Geometry"])
        parts.append(t)
    js = N("GeometryNodeJoinGeometry")
    for t in parts:
        L(t.outputs["Geometry"], js.inputs[0])
    inst = N("GeometryNodeInstanceOnPoints")
    L(mv.outputs["Geometry"], inst.inputs["Points"]); L(js.outputs["Geometry"], inst.inputs["Instance"])
    L(gi.outputs["Inv Scale"], inst.inputs["Scale"])
    j = N("GeometryNodeJoinGeometry")
    L(gi.outputs[0], j.inputs[0]); L(inst.outputs["Instances"], j.inputs[0])
    L(j.outputs[0], go.inputs[0])
    _GN["g"] = g
    _GN["ids"] = {it.name: it.identifier for it in g.interface.items_tree
                  if getattr(it, "in_out", "") == "INPUT"}
    return g


STATS = {"studs": 0, "objects": 0}


def studs(ob, nx, ny, size, centre, inv=(1.0, 1.0, 1.0)):
    """Instance an nx x ny stud grid (object space: size = grid extent, centre = grid centre on the top face)."""
    if nx < 1 or ny < 1:
        return None
    g = _stud_group()
    md = ob.modifiers.new("studs", "NODES")
    md.node_group = g
    ids = _GN["ids"]
    md[ids["Count X"]], md[ids["Count Y"]] = int(nx), int(ny)
    md[ids["Size"]] = (float(size[0]), float(size[1]), 0.0)
    md[ids["Centre"]] = tuple(float(v) for v in centre)
    md[ids["Inv Scale"]] = tuple(float(v) for v in inv)
    md.show_viewport = False            # render only: camera ray casts in build.py skip the studs
    STATS["studs"] += int(nx) * int(ny)
    STATS["objects"] += 1
    return md


def studs_box(ob, x0, x1, y0, y1, ztop):
    """Studs over a real-size (scale 1) top face, in object space, pitch U, centred."""
    nx, ny = int(floor((x1 - x0) / U + 1e-3)), int(floor((y1 - y0) / U + 1e-3))
    return studs(ob, nx, ny, ((nx - 1) * U, (ny - 1) * U), ((x0 + x1) / 2, (y0 + y1) / 2, ztop))


def studs_unit(ob, dims):
    """Studs on top of a unit-mesh object scaled to dims (setkit.bbox / core.part cube)."""
    sx, sy, sz = (max(1e-3, abs(d)) for d in dims)
    nx, ny = int(floor(sx / U + 1e-3)), int(floor(sy / U + 1e-3))
    return studs(ob, nx, ny, ((nx - 1) * U / sx, (ny - 1) * U / sy), (0, 0, 0.5), (1 / sx, 1 / sy, 1 / sz))


# names (suffixes) of set-dressing boxes that get a smooth tile top instead of studs
TILE_END = ("top", "table", "slab", "cslab", "kslab", "tdesk", "tray", "meal", "mat", "path", "lid", "cap",
            "tcasetop", "pan", "food", "screen", "board", "boardf", "cork", "corkf", "menu", "menuf", "roof_flat",
            "walk", "road", "court", "nb", "line")


def auto_studs(ob, dims, rot):
    """setkit.bbox hook: studs on the top of any flat-topped, unrotated box at least 1x1 stud big."""
    if not BRICK or ob.get("brick"):
        return
    if abs(rot[0]) > 0.5 or abs(rot[1]) > 0.5:
        return
    sx, sy, sz = (abs(d) for d in dims)
    if sz < 0.08 or ob.name.endswith(TILE_END) or any(c.isdigit() for c in ob.name[-1:]) and \
            ob.name.rstrip("0123456789.-").endswith(TILE_END):
        ob["brick"] = "tile"
        return
    if sx < 0.95 or sy < 0.95 or (ob.material_slots and ob.material_slots[0].link == "OBJECT"):
        return
    rz = abs(rot[2]) % 180
    if 5 < rz < 85 or 95 < rz < 175:            # skewed pieces (pillows, notes): no studs
        return
    ob["brick"] = "plate"
    studs_unit(ob, (sx, sy, sz))


# ---------------------------------------------------------------- walls (running bond, real seams)
def _snap(v, step, base=0.0):
    return base + round((v - base) / step) * step


def _cuts(a, b, phase, piece):
    """Joint positions inside [a, b] for a bond with joints at phase + k*piece; no sliver under 0.5."""
    k = floor((a - phase) / piece) + 1
    out = []
    x = phase + k * piece
    while x < b - 1e-6:
        if x - a >= 0.5 and b - x >= 0.5:
            out.append(x)
        x += piece
    return [a] + out + [b]


def _minus(a, b, holes):
    """[a, b] minus the given u intervals."""
    segs = [(a, b)]
    for h0, h1 in holes:
        nxt = []
        for s0, s1 in segs:
            if h1 <= s0 or h0 >= s1:
                nxt.append((s0, s1))
                continue
            if h0 - s0 > 0.05:
                nxt.append((s0, h0))
            if s1 - h1 > 0.05:
                nxt.append((h1, s1))
        segs = nxt
    return segs


def wall_rows(z0, H, holes):
    """Rows (z0, z1, course index) of bricks from z0 up to z0+H, cut where hole edges fall (snapped to plates)."""
    top = z0 + H
    bps = set()
    z, k = z0, 0
    courses = []
    while z < top - 1e-6:
        h = BRICK_H if z + BRICK_H <= top + 1e-6 else min(PLATE, top - z) if top - z >= 0.2 else top - z
        courses.append((z, min(top, z + h), k))
        z += h
        k += 1
    if courses and courses[-1][1] - courses[-1][0] < 0.15 and len(courses) > 1:     # merge a sliver cap
        a = courses.pop()
        b = courses.pop()
        courses.append((b[0], a[1], b[2]))
    for _, _, hz0, hz1 in holes:
        bps.add(hz0); bps.add(hz1)
    rows = []
    for c0, c1, k in courses:
        cuts = sorted([c0, c1] + [b for b in bps if c0 + 0.15 < b < c1 - 0.15])
        for a, b in zip(cuts, cuts[1:]):
            rows.append((a, b, k))
    return rows


def wall_blocks(add, u0, u1, a0, a1, z0, H, holes=(), piece=4.0, bands=(), seed=0):
    """Running-bond wall from u0..u1 (along local X), thickness a0..a1 (local Y), z0..z0+H, with window holes
    [(u0, u1, z0, z1)]. add(x0, x1, y0, y1, z0, z1, band) receives every brick; band = index into bands
    [(z_top, ...)] (bricks below a band's top go to that band; the rest to band len(bands))."""
    holes = [(_snap(h0, 0.5), _snap(h1, 0.5), _snap(hz0, PLATE, z0), _snap(hz1, PLATE, z0))
             for h0, h1, hz0, hz1 in holes]
    for r0, r1, k in wall_rows(z0, H, holes):
        zc = (r0 + r1) / 2
        hs = [(h0, h1) for h0, h1, hz0, hz1 in holes if hz0 < zc < hz1]
        band = next((i for i, b in enumerate(bands) if zc < b[0]), len(bands))
        phase = u0 + (piece / 2 if k % 2 else 0.0) + (1.0 if (k // 2 + seed) % 3 == 2 else 0.0)
        for s0, s1 in _minus(u0, u1, hs):
            cuts = _cuts(s0, s1, phase, piece)
            for a, b in zip(cuts, cuts[1:]):
                add(a, b, a0, a1, r0, r1, band)
    return holes


class Pending:
    """A brick wall waiting for its windows (setkit.window registers holes on the Wall frame first)."""

    def __init__(self, W, name, u0, u1, z0, H, col, T=1.0, room=True, front=None):
        self.W, self.name, self.u0, self.u1, self.z0, self.H, self.col, self.T = W, name, u0, u1, z0, H, col, T
        self.room, self.front = room, front          # front = room depth: also close the open front
        self.holes, self.bands = [], []


def defer_wall(s, W, name, u0, u1, z0, H, col, T=1.0, room=True, front=None):
    p = Pending(W, name, u0, u1, z0, H, col, T, room, front)
    W.brick = p
    if not hasattr(s, "pending"):
        s.pending = []
    s.pending.append(p)
    return p


def build_wall(p):
    """Build a pending wall as one object per colour band, at the Wall frame (local Y = into the wall)."""
    W = p.W
    bands = sorted(p.bands, key=lambda b: b[0])
    bands = [(_snap(top, BRICK_H, p.z0), col) for top, col in bands]
    bms = [bmesh.new() for _ in range(len(bands) + 1)]

    def add(x0, x1, y0, y1, z0, z1, band):
        block(bms[band], x0, x1, y0, y1, z0, z1)
    wall_blocks(add, p.u0, p.u1, 0.0, p.T, p.z0, p.H, p.holes, bands=bands, seed=len(p.name))
    loc = W.P(0, 0, 0)
    obs = []
    for i, bm in enumerate(bms):
        if not bm.faces:
            bm.free()
            continue
        nm = p.name if i == len(bands) else f"{p.name}w{i}"
        col = p.col if i == len(bands) else bands[i][1]
        ob = obj(nm, bm, loc, col, "wall", rz=W.rz)
        obs.append(ob)
    if obs:          # one row of studs along the top of the wall
        top = obs[-1] if len(obs) else None
        studs_box(top, p.u0, p.u1, 0.0, p.T, p.z0 + p.H)
    return obs


def finish_set(s):
    for p in getattr(s, "pending", []):
        build_wall(p)
        if p.front:
            front_wall(s, p)
    s.pending = []


def front_wall(s, back):
    """One-sided brick wall closing the room's open front (seen from inside on reverse angles; culled from
    outside, so the default wide cameras look straight in)."""
    d = back.front
    m = bpy.data.materials.get("BrickFront")
    if m is None:
        m = core.MAT_PLAIN.copy()
        m.name = "BrickFront"
        m.use_backface_culling = True
        if hasattr(m, "use_backface_culling_shadow"):
            m.use_backface_culling_shadow = True
    bm = bmesh.new()

    def add(x0, x1, y0, y1, z0, z1, band):
        # only the room-side face of each brick + its chamfer ring, as a thin skin facing +Y (into the room)
        fs = block(bm, x0, x1, -0.12, 0.0, z0, z1, c=CH)
        bad = [f for f in fs if f.normal.y < 0.6]
        bmesh.ops.delete(bm, geom=bad, context="FACES_ONLY")
    wall_blocks(add, back.u0, back.u1, 0, 1, back.z0, back.H, (), seed=3)
    ob = obj(f"{s.name}_front", bm, s.P(0, -d / 2, 0), back.col, "wall")
    ob.material_slots[0].link = "OBJECT"
    ob.material_slots[0].material = m
    ob.visible_shadow = False
    ob.hide_viewport = True          # render only: invisible to build.py's camera ray casts (like look.front_walls)
    ob["brickfront"] = True
    return ob


# ---------------------------------------------------------------- floors, baseplates, tabletop
def plate_obj(name, loc, x0, x1, y0, y1, z0, z1, col, kind="plate", stud=True, c=CH):
    bm = bmesh.new()
    block(bm, x0, x1, y0, y1, z0, z1, c=c)
    ob = obj(name, bm, loc, col, kind)
    if stud:
        studs_box(ob, x0, x1, y0, y1, z1)
    return ob


def baseplate(name, loc, x0, x1, y0, y1, z0, z1, col):
    """Studded baseplate made of 32x32 baseplates side by side (their joints show as seams)."""
    bm = bmesh.new()
    x = x0
    while x < x1 - 1e-6:
        xe = min(x1, x + 32)
        y = y0
        while y < y1 - 1e-6:
            ye = min(y1, y + 32)
            block(bm, x, xe, y, ye, z0, z1, c=0.04)
            y = ye
        x = xe
    ob = obj(name, bm, loc, col, "base")
    studs_box(ob, x0, x1, y0, y1, z1)
    return ob


def tiles_obj(name, loc, x0, x1, y0, y1, z0, z1, tx, ty, cols, stagger=False, kind="tile"):
    """Smooth tile floor: tx x ty tiles (checker over len(cols) colours; staggered rows = planks).
    One object per colour; the first keeps `name`."""
    bms = [bmesh.new() for _ in cols]
    j, y = 0, y0
    while y < y1 - 1e-6:
        ye = min(y1, y + ty)
        off = (tx / 2 if (stagger and j % 2) else 0.0)
        cuts = _cuts(x0, x1, x0 + off, tx)
        for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
            if len(cols) == 1:
                k = 0
            elif stagger:
                k = 1 if (i * 7 + j * 3) % 5 == 0 else 0
            else:
                k = (i + j) % len(cols)
            block(bms[int(k)], a, b, y, ye, z0, z1, c=0.035)
        y = ye
        j += 1
    obs = []
    for i, (bm, col) in enumerate(zip(bms, cols)):
        if not bm.faces:
            bm.free()
            continue
        obs.append(obj(name if i == 0 else f"{name}{i + 1}", bm, loc, col, kind))
    return obs


def table(span_x=(-90, 1180), span_y=(-80, 60)):
    """The real-world wooden tabletop all sets stand on (object 'ground', kept by name)."""
    x0, x1 = span_x
    y0, y1 = span_y
    bm = bmesh.new()
    block(bm, x0, x1, y0, y1, TABLE_Z - 3.0, TABLE_Z, c=0.6)
    ob = obj("ground", bm, (0, 0, 0), "#9A6A3E", "table")
    ob["tex"] = "wood"
    return ob


# ---------------------------------------------------------------- backdrop cards (the real-world hint)
_MAT = {}


def sky_card_mat():
    if "sky" in _MAT:
        return _MAT["sky"]
    m = bpy.data.materials.new("BrickSkyCard")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = lin("#DCEFFB")
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = lin("#5FA8E8")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.6
    b.inputs["Roughness"].default_value = 0.9           # printed card: matte paper
    b.inputs["Specular IOR Level"].default_value = 0.1
    _MAT["sky"] = m
    return m


def cloud_mat():
    if "cloud" in _MAT:
        return _MAT["cloud"]
    m = core.material("BrickCloud", color="#FFFFFF", emission=0.55, rough=0.9)
    _MAT["cloud"] = m
    return m


def glass_mat():
    if "glass" in _MAT:
        return _MAT["glass"]
    m = bpy.data.materials.new("BrickGlass")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = lin("#D8F0FF")
    b.inputs["Roughness"].default_value = 0.06
    b.inputs["Specular IOR Level"].default_value = 0.6
    b.inputs["Alpha"].default_value = 0.22
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    else:
        m.blend_method = "BLEND"
    _MAT["glass"] = m
    return m


def card(name, loc, w, h, rz=0.0, clouds=True, seed=0):
    """A printed sky card standing on the table: a thin board, gradient sky + a few flat printed clouds."""
    bm = bmesh.new()
    block(bm, -w / 2, w / 2, 0, 0.3, 0, h, c=0.1)
    ob = obj(name, bm, loc, "#9CCBF0", "backdrop", rz=rz, shadow=False)
    ob.hide_viewport = True              # render only: camera ray casts don't see it (camera logic unchanged)
    ob.material_slots[0].link = "OBJECT"
    ob.material_slots[0].material = sky_card_mat()
    if clouds:
        import random
        rnd = random.Random(seed)
        cb = bmesh.new()
        sc = min(1.0, w / 40)
        n = max(1, int(w / 22))
        for k in range(n):
            cx = -w / 2 + w * (k + 0.5) / n + rnd.uniform(-4, 4) * sc
            cz = h * rnd.uniform(0.5, 0.75)
            for j, (dx, dz, r) in enumerate(((0, 0, 3.2), (3.4, -0.6, 2.4), (-3.2, -0.7, 2.2), (1.2, 1.6, 2.2))):
                rr = r * rnd.uniform(0.8, 1.2) * sc
                _disc(cb, cx + dx * sc, cz + dz * sc, rr, -0.06 - 0.01 * j)
        co = obj(name + "cl", cb, loc, "#FFFFFF", "print", rz=rz, shadow=False)
        co.material_slots[0].link = "OBJECT"
        co.material_slots[0].material = cloud_mat()
        co.color = (1, 1, 1, 1)
        co["cloud"] = True
        co.hide_viewport = True
    return ob


def _disc(bm, x, z, r, y, seg=20):
    vs = [bm.verts.new((x + r * cos(2 * pi * i / seg), y, z + r * 0.62 * sin(2 * pi * i / seg))) for i in range(seg)]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.y > 0:
        f.normal_flip()


# ---------------------------------------------------------------- roofs (stacked slope bricks)
def roof(name, loc, L, D, H, col, piece=4.0, ridge_col=None):
    """Gable roof along X: courses of slope bricks stepping in from +-D at z 0 to a 1-stud ridge at the top.
    Each course has a small vertical lip, like real slope bricks; pieces are split along X (seams)."""
    n = max(2, int(round(H / BRICK_H)))
    run = (D - 0.5) / n
    bm = bmesh.new()
    xs = _cuts(-L / 2, L / 2, -L / 2, piece)
    for k in range(n):
        z0, z1 = k * BRICK_H, (k + 1) * BRICK_H
        yo, yi = D - k * run, D - (k + 1) * run
        lip = 0.25
        for side in (-1, 1):
            off = (piece / 2 if (k + (side > 0)) % 2 else 0)
            cs = _cuts(-L / 2, L / 2, -L / 2 + off, piece)
            for a, b in zip(cs, cs[1:]):
                poly = [(side * yi * 0.0, z0), (side * yo, z0), (side * yo, z0 + lip), (side * yi, z1),
                        (0.0, z1)]
                if side < 0:
                    poly = poly[::-1]
                wedge(bm, a + 0.02, b - 0.02, poly)
    # ridge: a row of 1-wide plates with studs
    zt = n * BRICK_H
    rb = bmesh.new()
    for a, b in zip(xs, xs[1:]):
        block(rb, a, b, -0.5, 0.5, zt, zt + PLATE, c=0.04)
    x = -L / 2 + 0.5
    while x < L / 2 - 0.4:
        stud(rb, x, 0, zt + PLATE)
        x += U
    ob = obj(name, bm, loc, col, "slope")
    obj(name + "ridge", rb, loc, ridge_col or col, "plate")
    return ob, zt


# ---------------------------------------------------------------- trees, bushes, plants (round bricks)
def round_stack(bm, x, y, z, layers, seg=24, stud_ring=True):
    """layers: [(radius, height)] stacked from z up. Studs ring the exposed top of each layer."""
    zz = z
    for i, (r, h) in enumerate(layers):
        cyl(bm, x, y, zz, zz + h, r, seg=seg)
        nxt = layers[i + 1][0] if i + 1 < len(layers) else 0.0
        zz += h
        if stud_ring and r - nxt >= 0.75:
            rr = r - 0.5
            n = max(1, int(2 * pi * rr / 1.15))
            for k in range(n):
                a = 2 * pi * (k + 0.5 * (i % 2)) / n
                stud(bm, x + rr * cos(a), y + rr * sin(a), zz)
        elif stud_ring and i == len(layers) - 1:
            if r >= 0.75:
                for k in range(4):
                    a = pi / 4 + k * pi / 2
                    stud(bm, x + 0.5 * r * cos(a), y + 0.5 * r * sin(a), zz)
            else:
                stud(bm, x, y, zz)
    return zz


def tree(s, x, y, k=1.0, seed=0, leaf="#2E8B3A"):
    """Trunk of stacked 2x2 round bricks; canopy of round leaf plates (ball) or square plates (pine)."""
    import random
    rnd = random.Random(seed * 131 + int(x * 7) + int(y * 13))
    nm = f"{s.name}_trunk{x}{y}"
    n_tr = max(2, int(round(4.0 * k / BRICK_H)))
    bm = bmesh.new()
    zt = round_stack(bm, 0, 0, 0, [(1.0, BRICK_H)] * n_tr, seg=16, stud_ring=False)
    obj(nm, bm, s.P(x, y, 0), "#6E4423", "round")
    cols = [leaf, core.shade(leaf, 0.82), core.shade(leaf, 1.12)]
    if seed % 3 == 2:            # pine: square plates rotated 45 deg every other layer, shrinking upward
        bms = [bmesh.new(), bmesh.new()]
        z = zt - 0.4
        sizes = [6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 1]
        for i, w in enumerate(sizes):
            w = w * k
            h = PLATE * 2 if i % 2 == 0 else PLATE
            b = bms[i % 2]
            fs = block(b, -w / 2, w / 2, -w / 2, w / 2, z, z + h)
            if i % 2:
                bmesh.ops.rotate(b, verts=list({v for f in fs for v in f.verts}), cent=(0, 0, 0),
                                 matrix=__import__("mathutils").Matrix.Rotation(pi / 4, 3, "Z"))
            z += h
        stud(bms[0], 0, 0, z)
        for i, b in enumerate(bms):
            obj(f"{s.name}_leaf{x}{y}" + ("" if i == 0 else f"_{i}"), b, s.P(x, y, 0), cols[i], "round")
        return
    # ball tree: round leaf plates/bricks approximating a sphere, two shades in alternate layers
    R = 3.5 * k
    zc = zt + R * 0.75
    bms = [bmesh.new(), bmesh.new()]
    z = zc - R
    i = 0
    while z < zc + R - 0.3:
        h = BRICK_H if abs(z + 0.6 - zc) < R * 0.55 else PLATE * 2
        zm = z + h / 2
        r = sqrt(max(0.5, R * R - (zm - zc) ** 2))
        r = max(1.0, round(r * 2) / 2)
        nxt_zm = z + h + 0.4
        rn = sqrt(max(0.0, R * R - (nxt_zm - zc) ** 2)) if nxt_zm < zc + R else 0.0
        cyl(bms[i % 2], 0, 0, z, z + h, r, seg=28)
        if zm > zc and r - rn >= 0.7:                       # studs on the exposed ring of the upper half
            rr = r - 0.5
            n = max(1, int(2 * pi * rr / 1.2))
            for j in range(n):
                a = 2 * pi * (j + 0.5 * (i % 2)) / n + rnd.uniform(-0.05, 0.05)
                stud(bms[i % 2], rr * cos(a), rr * sin(a), z + h)
        z += h
        i += 1
    stud(bms[(i - 1) % 2], 0, 0, z)
    for j, b in enumerate(bms):
        obj(f"{s.name}_leaf{x}{y}" + ("" if j == 0 else f"_{j}"), b, s.P(x, y, 0),
            cols[j] if j == 0 else cols[1 + (seed % 2)], "round")


def bush(s, nm, x, y, k=1.0, col="#2F8F3E", seed=0):
    """Two or three round leaf bricks side by side, stepped up in the middle."""
    bm = bmesh.new()
    for j, (dx, rr, layers) in enumerate(((0, 1.6, 2), (-1.7, 1.2, 1), (1.7, 1.2, 1))):
        r = max(1.0, round(rr * k * 2) / 2)
        round_stack(bm, dx * k, 0, 0, [(r, BRICK_H)] * layers + [(r * 0.6, PLATE)])
    obj(f"{s.name}_{nm}0", bm, s.P(x, y, 0), core.shade(col, 0.92 + 0.08 * (seed % 3)), "round")


def plant(s, nm, x, y, k=1.0, pot="#C8643B", leaf="#2F8F3E", z=0.0):
    """Potted plant: round-brick pot, then green leaf plates fanned in tiers."""
    pr = max(0.5, round(0.75 * k * 2) / 2)
    bm = bmesh.new()
    zt = round_stack(bm, 0, 0, 0, [(pr * 0.85, BRICK_H * k), (pr, PLATE)], seg=18, stud_ring=False)
    obj(f"{s.name}_{nm}pot", bm, s.P(x, y, z), pot, "round")
    lb = bmesh.new()
    zz = zt
    for i, (r, h) in enumerate(((pr * 1.4, PLATE), (pr * 1.7, PLATE), (pr * 1.3, BRICK_H * 0.66),
                                (pr * 0.8, PLATE))):
        cyl(lb, 0, 0, zz, zz + h, max(0.4, r), seg=10 if i % 2 else 8)
        zz += h
    stud(lb, 0, 0, zz)
    obj(f"{s.name}_{nm}lf0", lb, s.P(x, y, z), leaf, "round")


def tall_plant(s, nm, x, y, k=1.0, pot="#F4F4F4", leaf="#2F8F3E"):
    """Floor plant: round pot, a stem of 1x1 round bricks, and stacked leaf plates."""
    bm = bmesh.new()
    zt = round_stack(bm, 0, 0, 0, [(0.85 * k, BRICK_H), (1.0 * k, PLATE)], seg=18, stud_ring=False)
    obj(f"{s.name}_{nm}pot", bm, s.P(x, y, 0), pot, "round")
    lb = bmesh.new()
    z = zt
    for i in range(int(3 * k) + 2):
        cyl(lb, 0, 0, z, z + BRICK_H, 0.3, seg=10)
        z += BRICK_H
    z0 = zt + 1.2
    for i, r in enumerate((1.6, 1.9, 1.5, 1.1, 0.7)):
        zz = z0 + i * (z - z0) / 5
        b = block(lb, -r * k, r * k, -r * k * 0.45, r * k * 0.45, zz, zz + PLATE)
        bmesh.ops.rotate(lb, verts=list({v for f in b for v in f.verts}), cent=(0, 0, 0),
                         matrix=__import__("mathutils").Matrix.Rotation(i * 1.1, 3, "Z"))
    stud(lb, 0, 0, z)
    obj(f"{s.name}_{nm}lf0", lb, s.P(x, y, 0), leaf, "round")


def silo(name, loc, r, h, col, top_col):
    """Silo: stacked round bricks + a dome of shrinking round plates."""
    bm = bmesh.new()
    n = int(h / BRICK_H)
    round_stack(bm, 0, 0, 0, [(r, BRICK_H)] * n, seg=36, stud_ring=False)
    ob = obj(name, bm, loc, col, "round")
    tb = bmesh.new()
    z = n * BRICK_H
    lay = []
    for i in range(6):
        lay.append((max(0.6, r * cos(i * pi / 12)), PLATE * 2))
    round_stack(tb, 0, 0, z, lay, seg=36)
    obj(name + "top", tb, loc, top_col, "round")
    return ob
