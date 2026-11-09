"""Channel looks (runs inside Blender), picked with MILO_LOOK:
  base   flat toy plastic, spec lighting (what Season 1 v1 used)
  toon   cel shading in 3 hard steps with purple-tinted shadows, plus black ink outlines
  brand  toon + the Milo grade (warm highlights, purple-blue lift, punchier colour, glow on bright
         things) + Milo's pendant glows and flashes whenever a rule hits him"""
import bpy
from math import radians, sin, cos
import core
from core import lin, keys, frame

OUTLINE = 0.07           # ink line thickness in world units (user asked for thicker lines, 2026-11-07)


def _toon_tree(mat, ramp_cols):
    """Rewire a Principled material: Diffuse -> Shader to RGB -> 3-step ramp, times the base colour,
    shown as emission (flat, exact brand colours), keeping alpha for ghosts."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    base_link = next((l for l in nt.links if l.to_socket == bsdf.inputs["Base Color"]), None)
    alpha_link = next((l for l in nt.links if l.to_socket == bsdf.inputs["Alpha"]), None)
    base = base_link.from_socket if base_link else None
    base_val = tuple(bsdf.inputs["Base Color"].default_value)
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, ramp_cols[0]
    els[1].position, els[1].color = 0.32, ramp_cols[1]
    e = els.new(0.85)
    e.color = ramp_cols[2]
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    if base:
        nt.links.new(base, mix.inputs[6])
    else:
        mix.inputs[6].default_value = base_val
    em = nt.nodes.new("ShaderNodeEmission")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    ms = nt.nodes.new("ShaderNodeMixShader")
    L = nt.links.new
    L(dif.outputs[0], s2r.inputs[0]); L(s2r.outputs["Color"], bw.inputs[0]); L(bw.outputs[0], ramp.inputs[0])
    L(ramp.outputs["Color"], mix.inputs[7]); L(mix.outputs[2], em.inputs["Color"])
    if alpha_link:
        L(alpha_link.from_socket, ms.inputs[0])
    else:
        ms.inputs[0].default_value = 1.0
    L(tr.outputs[0], ms.inputs[1]); L(em.outputs[0], ms.inputs[2])
    L(ms.outputs[0], out.inputs["Surface"])


def toon(grade_shadows):
    shade = [(0.42, 0.36, 0.64, 1), (0.80, 0.76, 0.90, 1), (1.0, 0.98, 0.94, 1)] if grade_shadows else \
            [(0.45, 0.45, 0.48, 1), (0.80, 0.80, 0.82, 1), (1.0, 1.0, 1.0, 1)]
    for m in bpy.data.materials:
        if m.name in ("Plain", "Head", "Grass"):
            _toon_tree(m, shade)
    ink = bpy.data.materials.new("Ink")
    ink.use_nodes = True
    nt = ink.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.02, 0.015, 0.03, 1)
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    ink.use_backface_culling = True
    if hasattr(ink, "use_backface_culling_shadow"):
        ink.use_backface_culling_shadow = True
    done = set()
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.name == "ground" or ob.name.startswith(("puff", "pollen", "mote", "cloud")):
            continue
        if any(s.link == "OBJECT" for s in ob.material_slots):
            continue
        sc = ob.scale
        if min(sc) < 0.15 or "_cord" in ob.name:
            continue                       # hair-thin parts would grow fat ink blobs
        me = ob.data
        if me.name not in done:
            me.materials.append(ink)
            done.add(me.name)
        mod = ob.modifiers.new("ink", "SOLIDIFY")
        mod.thickness = min(0.3, OUTLINE / (sum(sc) / 3))
        mod.offset = 1.0
        mod.use_flip_normals = True
        mod.use_rim = False
        mod.material_offset = len(me.materials) - 1


def grade(sc):
    sc.use_nodes = True
    nt = sc.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    cb = nt.nodes.new("CompositorNodeColorBalance")
    cb.correction_method = "LIFT_GAMMA_GAIN"
    cb.lift = (0.96, 0.94, 1.08)       # purple-blue in the darks
    cb.gain = (1.07, 1.01, 0.93)       # warm golden highlights
    hsv = nt.nodes.new("CompositorNodeHueSat")
    hsv.inputs["Saturation"].default_value = 1.14
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    if hasattr(glare, "threshold"):
        glare.threshold = 0.98
    elif "Threshold" in glare.inputs:
        glare.inputs["Threshold"].default_value = 0.98
    comp = nt.nodes.new("CompositorNodeComposite")
    L = nt.links.new
    L(rl.outputs["Image"], cb.inputs["Image"]); L(cb.outputs["Image"], hsv.inputs["Image"])
    L(hsv.outputs["Image"], glare.inputs["Image"]); L(glare.outputs["Image"], comp.inputs["Image"])


def pendant(C, nf):
    """Milo's pendant glows softly, and flashes hot whenever his form changes (a rule hits him)."""
    if "milo" not in C:
        return
    gem = bpy.data.objects.get("milo_pendantgem")
    if gem is None:
        return
    m = bpy.data.materials.new("Gem")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    nt.links.new(oi.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(oi.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 3.0
    gem.material_slots[0].link = "OBJECT"
    gem.material_slots[0].material = m
    hits = sorted({frame(t) for t, _ in C["milo"].wears if t > 0})
    frames = list(range(nf))
    lvl = []
    for f in frames:
        k = 0.35
        for h in hits:
            if 0 <= f - h < 18:
                k = max(k, 1.0 - (f - h) / 18 * 0.65)
        lvl.append(k)
    for ci, base in enumerate((0.95, 0.05, 0.06)):
        keys(gem, "color", ci, frames, [base * k for k in lvl])


# ---------------------------------------------------------------- "real": the top-channel 3D look
# Built from the reference study (a study of top animated story Shorts): soft sun + bright sky fill, AO,
# photo-textured floors/paths, flat pastel walls, AgX medium-high contrast, light bloom, 70 deg lens.
import os
import numpy as np
import textures

SET_FLOOR = {"home": "wood", "classroom": "marble", "hallway": "terrazzo", "cafeteria": "tiles", "gym": "planks",
             "museum": "marble", "theater": "carpet"}
TINT = {"wood": 0.0, "marble": 0.0, "terrazzo": 0.15, "tiles": 0.7, "planks": 0.0, "carpet": 1.0, "cobble": 0.0,
        "asphalt": 0.0, "grass": 1.0, "brick": 0.0, "plaster": 1.0, "denim": 1.0}
REAL = dict(sun=5.0, sun_angle=6.0, sky=0.8, look="AgX - Medium High Contrast", exposure=0.32,
            bloom=0.25, sat=1.04, rough=0.5, sky_neutral=0.8, contrast=24.0, bright=0.0,
            room_light=2.5)
import json as _json
REAL.update(_json.loads(os.environ.get("MILO_REAL", "{}")))      # tuning overrides for look tests
_tex_cache = {}
GLOSSY = {"marble": 0.35, "terrazzo": 0.45, "tiles": 0.4, "wood": 0.55, "planks": 0.6}


def _img_mean(img):
    px = np.empty(len(img.pixels), np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(-1, 4)[:, :3].mean(0)


def tex_material(role):
    """Box-projected world-space photo texture (colour, normal, roughness). TINT blends toward the
    object's own colour (texture detail kept, hue from the object) so one material serves every part."""
    if role in _tex_cache:
        return _tex_cache[role]
    pid, rep = textures.TEX[role]
    pth = textures.paths(role)
    m = bpy.data.materials.new("Tex_" + role)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Specular IOR Level"].default_value = 0.4
    L = nt.links.new
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (rep / 4.0,) * 3
    L(geo.outputs["Position"], mp.inputs["Vector"])

    def img(kind, non_color=False):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(pth[kind], check_existing=True)
        if non_color:
            t.image.colorspace_settings.name = "Non-Color"
        t.projection, t.projection_blend = "BOX", 0.2
        L(mp.outputs["Vector"], t.inputs["Vector"])
        return t
    dif, nor, rgh = img("diff"), img("nor", True), img("rough", True)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.7
    L(nor.outputs["Color"], nm.inputs["Color"]); L(nm.outputs["Normal"], b.inputs["Normal"])
    if role in GLOSSY:                    # polished floors/furniture reflect like the references
        rm = nt.nodes.new("ShaderNodeMath"); rm.operation = "MULTIPLY"
        rm.inputs[1].default_value = GLOSSY[role]
        L(rgh.outputs["Color"], rm.inputs[0]); L(rm.outputs[0], b.inputs["Roughness"])
    else:
        L(rgh.outputs["Color"], b.inputs["Roughness"])
    k = TINT.get(role, 0.0)
    if k > 0:                     # keep the texture's light/dark detail, take the hue from the object
        mean = _img_mean(dif.image)
        lum = float(mean @ np.array([0.2126, 0.7152, 0.0722], np.float32))
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        L(dif.outputs["Color"], bw.inputs[0])
        dv = nt.nodes.new("ShaderNodeMath"); dv.operation = "DIVIDE"; dv.inputs[1].default_value = max(lum, 1e-3)
        L(bw.outputs[0], dv.inputs[0])
        mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "SCALE"
        L(oi.outputs["Color"], mul.inputs[0]); L(dv.outputs[0], mul.inputs["Scale"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["Factor"].default_value = k
        L(dif.outputs["Color"], mix.inputs[6]); L(mul.outputs[0], mix.inputs[7])
        L(mix.outputs[2], b.inputs["Base Color"])
    else:
        L(dif.outputs["Color"], b.inputs["Base Color"])
    _tex_cache[role] = m
    return m


def _set_obj_mat(ob, m):
    if not ob.material_slots:
        return
    ob.material_slots[0].link = "OBJECT"
    ob.material_slots[0].material = m


def texture_world():
    """Pick textures by object name (sets are built with predictable names)."""
    import re
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        n = ob.name
        role = ob.get("tex")                 # a set piece can ask for a texture role directly
        if role:
            _set_obj_mat(ob, tex_material(role))
            continue
        st = n.split("_", 1)[0]
        if n.endswith("_floor") and st in SET_FLOOR:
            role = SET_FLOOR[st]
        elif n.endswith("_rug"):
            role = "carpet"
        elif n == "street_walk":
            role = "cobble"
        elif n == "street_road":
            role = "asphalt"
        elif n == "ground":
            role = "grass"
        elif re.search(r"(top|table|tdesk|tdeskb|tvstand|bench)$", n) or re.match(r"cafeteria_t\d\d$", n):
            role = "planks"
        elif re.match(r"street_h\d$", n):
            role = "plaster"
        elif re.search(r"_leg\d$", n):
            role = "denim"
        if role:
            _set_obj_mat(ob, tex_material(role))


def _proc_material(name, kind):
    """Object-colour plastic with procedural detail: 'cloth' = soft folds + weave bump,
    'hair' = strands along the part, darker at the root, a bit glossy."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    L = nt.links.new
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    L(tc.outputs["Object"], wave.inputs["Vector"]); L(tc.outputs["Object"], nz.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    bump = nt.nodes.new("ShaderNodeBump")
    if kind == "cloth":
        wave.wave_type, wave.bands_direction = "BANDS", "Z"
        wave.inputs["Scale"].default_value, wave.inputs["Distortion"].default_value = 0.9, 4.0
        wave.inputs["Detail"].default_value = 2.0
        nz.inputs["Scale"].default_value = 140.0
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.94, 1.0
        b.inputs["Roughness"].default_value = 0.75
        bump.inputs["Strength"].default_value = 0.12
        L(wave.outputs["Fac"], mr.inputs["Value"]); L(nz.outputs["Fac"], bump.inputs["Height"])
    else:
        wave.wave_type, wave.bands_direction = "BANDS", "X"
        wave.inputs["Scale"].default_value, wave.inputs["Distortion"].default_value = 9.0, 2.5
        wave.inputs["Detail"].default_value = 3.0
        nz.inputs["Scale"].default_value = 3.0
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.72, 1.05
        b.inputs["Roughness"].default_value = 0.38
        b.inputs["Specular IOR Level"].default_value = 0.6
        bump.inputs["Strength"].default_value = 0.25
        L(wave.outputs["Fac"], mr.inputs["Value"]); L(wave.outputs["Fac"], bump.inputs["Height"])
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    L(oi.outputs["Color"], sc.inputs[0]); L(mr.outputs["Result"], sc.inputs["Scale"])
    L(sc.outputs[0], b.inputs["Base Color"]); L(bump.outputs["Normal"], b.inputs["Normal"])
    L(oi.outputs["Alpha"], b.inputs["Alpha"])
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"
    return m


def shirt_material(cloth):
    """Cloth + a printed graphic on the torso front (work/prints/atlas.png, picked per object by 'shirt')."""
    m = cloth.copy()
    m.name = "Shirt"
    nt = m.node_tree
    L = nt.links.new
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    base = next(l for l in nt.links if l.to_socket == b.inputs["Base Color"]).from_socket
    img = bpy.data.images.load(os.path.join(core.MILO, "work", "prints", "atlas.png"), check_existing=True)
    n = img.size[1] // img.size[0]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L(tc.outputs["Generated"], sep.inputs[0])

    def M(op, a, b_=None):
        k = nt.nodes.new("ShaderNodeMath"); k.operation = op
        for i, v in enumerate((a, b_)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                k.inputs[i].default_value = v
            else:
                L(v, k.inputs[i])
        return k.outputs[0]
    u = M("DIVIDE", M("SUBTRACT", sep.outputs["X"], 0.2), 0.6)
    v = M("DIVIDE", M("SUBTRACT", sep.outputs["Z"], 0.3), 0.6)
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_type, attr.attribute_name = "OBJECT", "shirt"
    va = M("DIVIDE", M("ADD", v, M("SUBTRACT", float(n - 1), attr.outputs["Fac"])), float(n))
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    L(u, comb.inputs[0]); L(va, comb.inputs[1])
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image, tex.extension = img, "CLIP"
    L(comb.outputs[0], tex.inputs[0])
    inside = M("MULTIPLY", M("MULTIPLY", M("GREATER_THAN", u, 0.0), M("LESS_THAN", u, 1.0)),
               M("MULTIPLY", M("GREATER_THAN", v, 0.0), M("LESS_THAN", v, 1.0)))
    front = M("LESS_THAN", sep.outputs["Y"], 0.03)
    a = M("MULTIPLY", M("MULTIPLY", tex.outputs["Alpha"], inside), front)
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L(a, mix.inputs["Factor"]); L(base, mix.inputs[6]); L(tex.outputs["Color"], mix.inputs[7])
    L(mix.outputs[2], b.inputs["Base Color"])
    return m


PRINT_OF = {"milo": 0}


def _print_for(name):
    if name in PRINT_OF:
        return PRINT_OF[name]
    return 1 + sum(map(ord, name)) % 7


HAIR_RE = r"_(hair|hl\d+|spike\d+|mspike\d+|curl\d|swoop|bun|pt\d|long|afro|pig.*)$"
CLOTH_RE = r"_(torso|jacket.*|vest.*|slv\d)$"


def dress():
    import re
    cloth, hair = _proc_material("Cloth", "cloth"), _proc_material("Hair", "hair")
    shirt = shirt_material(cloth)
    for ob in bpy.data.objects:
        if ob.type != "MESH" or not ob.material_slots or ob.material_slots[0].link == "OBJECT":
            continue
        if ob.material_slots[0].material is None or ob.material_slots[0].material.name != "Plain":
            continue
        if re.search(HAIR_RE, ob.name):
            _set_obj_mat(ob, hair)
        elif ob.name.endswith("_torso"):
            ob["shirt"] = float(_print_for(ob.name[:-6]))
            _set_obj_mat(ob, shirt)
        elif re.search(CLOTH_RE, ob.name):
            _set_obj_mat(ob, cloth)


def plastic():
    """Toy-plastic characters/props: a touch more spec + clearcoat sheen, 8% darker toward the bottom of
    every part (gradient on the part's own height), so flat colours get form."""
    for name in ("Plain", "Head"):
        m = bpy.data.materials.get(name)
        if not m:
            continue
        nt = m.node_tree
        b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Roughness"].default_value = REAL["rough"]
        b.inputs["Specular IOR Level"].default_value = 0.5
        if "Coat Weight" in b.inputs:
            b.inputs["Coat Weight"].default_value = 0.12
        if name != "Plain":
            continue
        link = next((l for l in nt.links if l.to_socket == b.inputs["Base Color"]), None)
        if not link:
            continue
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Generated"], sep.inputs[0])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.9, 1.0
        nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
        mul = nt.nodes.new("ShaderNodeVectorMath")
        mul.operation = "SCALE"
        nt.links.new(link.from_socket, mul.inputs[0]); nt.links.new(mr.outputs["Result"], mul.inputs["Scale"])
        nt.links.new(mul.outputs[0], b.inputs["Base Color"])


def real_render(sc):
    ee = sc.eevee
    for attr, val in (("use_shadows", True), ("use_raytracing", True), ("shadow_ray_count", 2),
                      ("shadow_step_count", 12), ("use_fast_gi", True), ("fast_gi_method", "GLOBAL_ILLUMINATION"),
                      ("fast_gi_distance", 3.0), ("fast_gi_ray_count", 4), ("fast_gi_step_count", 8),
                      ("use_gtao", True), ("gtao_distance", 1.0)):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except (TypeError, ValueError):
                pass
    sc.render.filter_size = 1.5
    vs = sc.view_settings
    vs.view_transform = "AgX"
    try:
        vs.look = REAL["look"]
    except TypeError:
        pass
    vs.exposure = REAL["exposure"]
    sun = bpy.data.objects.get("Sun")
    if sun:
        sun.data.energy = REAL["sun"]
        sun.data.angle = radians(REAL["sun_angle"])
        for attr, val in (("shadow_filter_radius", 1.5), ("shadow_maximum_resolution", 0.001)):
            if hasattr(sun.data, attr):
                setattr(sun.data, attr, val)
    w = sc.world
    if w:
        nt = w.node_tree
        lp = next(n for n in nt.nodes if n.type == "LIGHT_PATH")
        mixs = next(n for n in nt.nodes if n.type == "MIX_SHADER")
        light_bg = mixs.inputs[1].links[0].from_node      # the background that lights the scene
        light_bg.inputs["Strength"].default_value = REAL["sky"]
        if REAL["sky_neutral"] > 0:                        # warm-neutral fill so shadows aren't sky-blue
            src = light_bg.inputs["Color"].links[0].from_socket
            mx = nt.nodes.new("ShaderNodeMix")
            mx.data_type = "RGBA"
            mx.inputs["Factor"].default_value = REAL["sky_neutral"]
            mx.inputs[7].default_value = (0.95, 0.9, 0.82, 1)
            nt.links.new(src, mx.inputs[6])
            nt.links.new(mx.outputs[2], light_bg.inputs["Color"])


def room_lights():
    """A big soft panel under every ceiling: bright, even interiors with soft contact shadows."""
    for ob in list(bpy.data.objects):
        if not ob.name.endswith("_ceil"):
            continue
        w, d = ob.scale.x, ob.scale.y
        ld = bpy.data.lights.new(ob.name + "_panel", "AREA")
        ld.shape, ld.size, ld.size_y = "RECTANGLE", w * 0.8, d * 0.8
        ld.energy = REAL["room_light"] * w * d
        ld.color = (1.0, 0.99, 0.97)
        if hasattr(ld, "shadow_jitter"):
            pass
        lo = bpy.data.objects.new(ob.name + "_panel", ld)
        core.COLL.objects.link(lo)
        lo.location = (ob.location.x, ob.location.y, ob.location.z - 0.3)
        ob.color = (0.84, 0.84, 0.83, 1)          # clean white acoustic-tile ceiling (no concrete texture)
        if "tex" in ob:
            del ob["tex"]


def front_walls():
    """Close each room's open front with a one-sided wall: seen from inside (reverse angles, OTS) it is a
    wall; from outside (the default wide cameras) its back face is culled, so it is invisible."""
    import bmesh
    base = bpy.data.materials.get("Plain")
    if base is None:
        return
    m = base.copy()
    m.name = "FrontWall"
    m.use_backface_culling = True
    for ob in list(bpy.data.objects):
        if not ob.name.endswith("_ceil"):
            continue
        st = ob.name[:-5]
        back = bpy.data.objects.get(st + "_back") or bpy.data.objects.get(st + "_wall")
        w, d, h = ob.scale.x, ob.scale.y, ob.location.z
        y = ob.location.y - d / 2
        me = bpy.data.meshes.new(st + "_front")
        bm = bmesh.new()
        vs = [bm.verts.new(v) for v in ((-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h))]
        f = bm.faces.new(vs)
        f.normal_update()
        if f.normal.y < 0:                       # face the room (+Y)
            f.normal_flip()
        bm.to_mesh(me); bm.free()
        me.materials.append(m)
        fo = bpy.data.objects.new(st + "_front", me)
        core.COLL.objects.link(fo)
        fo.location = (ob.location.x, y, 0)
        fo.color = back.color if back else (0.9, 0.88, 0.84, 1)
        fo.visible_shadow = False


def real_grade(sc):
    sc.use_nodes = True
    nt = sc.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "BLOOM"
    for k, v in (("Threshold", 1.0), ("Strength", REAL["bloom"]), ("Size", 0.5)):
        if k in glare.inputs:
            glare.inputs[k].default_value = v
    if hasattr(glare, "quality"):
        glare.quality = "HIGH"
    hsv = nt.nodes.new("CompositorNodeHueSat")
    hsv.inputs["Saturation"].default_value = REAL["sat"]
    bc = nt.nodes.new("CompositorNodeBrightContrast")
    bc.inputs["Bright"].default_value = REAL["bright"]
    bc.inputs["Contrast"].default_value = REAL["contrast"]
    comp = nt.nodes.new("CompositorNodeComposite")
    L = nt.links.new
    L(rl.outputs["Image"], glare.inputs["Image"]); L(glare.outputs["Image"], hsv.inputs["Image"])
    L(hsv.outputs["Image"], bc.inputs["Image"]); L(bc.outputs["Image"], comp.inputs["Image"])


# ---------------------------------------------------------------- "brick": a tabletop stop-motion brickfilm
# ABS toy plastic everywhere, desk softboxes (3800-4500 K) re-set per shot like an animator's lights, warm
# practicals, AgX toy grade, macro DOF (build.dof_keys), and the stop-motion pass: every channel held on twos
# (threes on slow beats) per shot, a tiny frozen-until-touched placement error per pose, exposure flicker.
BRICK = dict(
    look="AgX - Medium High Contrast", exposure=-0.3, ambient=0.35, sun=0.8, sun_angle=28.0,
    key=2.8, key_k=4300, fill=0.38, fill_k=4700, rim=0.9, rim_k=4000, soft=0.75,     # irradiance-ish, Kelvin
    practical=60.0, practical_k=2700,
    rough=0.3, coat=0.18, sss=0.1, spec=0.5,                                          # ABS plastic
    bloom=0.3, sat=1.06, contrast=10.0, warm=0.04,                                    # grade
    hold=2, threes=["QUIET"], jit_pos=0.02, jit_rot=0.4, cam_jit=0.0, flicker=0.05,   # stop motion
    move_pos=0.04, move_rot=1.5,
    lens={"close": 38.0, "med": 46.0, "two": 50.0, "low": 50.0, "high": 48.0, "wide": 56.0},   # vertical FOV
    push=0.5,                                                                          # slower push-ins
    dof_k=150.0, focus_front=0.55,                                                     # 6-unit figure = 4 cm toy
    stops={"insert": 4.0, "pov": 5.6, "top": 5.6, "close": 4.0, "ots": 5.6, "fg": 5.6, "med": 5.6,
           "low": 5.6, "high": 5.6, "two": 8.0, "wide": 11.0, "slide": 11.0},
    foley=True,
)
BRICK.update(_json.loads(os.environ.get("MILO_BRICK", "{}")))      # tuning overrides for look tests
CLEAR_RE = r"(glass|water|_win$|lite$|_gl$|ice$)"       # transparent pieces (or ob["clear"] = 1)
SKIP_MATS = ("Puff", "Glow", "Star", "Pollen", "Gem", "Ink", "FrontWall")


def _kelvin(k):
    """Approximate blackbody colour (linear RGB, max 1) for lights when the temperature API is missing."""
    import math as m
    t = k / 100.0
    r = 255.0 if t <= 66 else 329.7 * (t - 60) ** -0.1332
    g = 99.47 * m.log(t) - 161.12 if t <= 66 else 288.12 * (t - 60) ** -0.0755
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.52 * m.log(t - 10) - 305.04)
    c = [max(0.0, min(255.0, v)) / 255 for v in (r, g, b)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return tuple(v / max(c) for v in c)


def _light(name, kind, kelvin):
    ld = bpy.data.lights.new(name, kind)
    if hasattr(ld, "use_temperature"):
        ld.use_temperature, ld.temperature = True, kelvin
    else:
        ld.color = _kelvin(kelvin)
    lo = bpy.data.objects.new(name, ld)
    core.COLL.objects.link(lo)
    return lo


def _abs_detail(nt):
    """Roughness for ABS plastic: base ~0.3 with soft fingerprint smudges and a few fine scuffs (world space,
    so every part shares the same scale), plus a whisper of bump so reflections are not CG-perfect."""
    L = nt.links.new
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    fp = nt.nodes.new("ShaderNodeTexNoise")
    fp.inputs["Scale"].default_value, fp.inputs["Detail"].default_value = 2.6, 3.0
    sc = nt.nodes.new("ShaderNodeTexNoise")
    sc.inputs["Scale"].default_value, sc.inputs["Detail"].default_value = 28.0, 8.0
    if "Distortion" in sc.inputs:
        sc.inputs["Distortion"].default_value = 2.0
    L(geo.outputs["Position"], fp.inputs["Vector"]); L(geo.outputs["Position"], sc.inputs["Vector"])
    r = BRICK["rough"]
    m1 = nt.nodes.new("ShaderNodeMapRange")
    m1.inputs["From Min"].default_value, m1.inputs["From Max"].default_value = 0.35, 0.65
    m1.inputs["To Min"].default_value, m1.inputs["To Max"].default_value = r - 0.06, r + 0.08
    L(fp.outputs["Fac"], m1.inputs["Value"])
    m2 = nt.nodes.new("ShaderNodeMapRange")
    m2.inputs["From Min"].default_value, m2.inputs["From Max"].default_value = 0.66, 0.74
    m2.inputs["To Min"].default_value, m2.inputs["To Max"].default_value = 0.0, 0.12
    L(sc.outputs["Fac"], m2.inputs["Value"])
    add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"; add.use_clamp = True
    L(m1.outputs["Result"], add.inputs[0]); L(m2.outputs["Result"], add.inputs[1])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.025
    L(sc.outputs["Fac"], bump.inputs["Height"])
    return add.outputs[0], bump.outputs["Normal"]


def _abs(m):
    """Turn a Principled material into injection-moulded ABS: roughness ~0.3 with smudges, specular 0.5,
    a light clearcoat, and a faint subsurface glow on light colours (from the object colour)."""
    if not m.use_nodes:
        return
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None or m.get("abs"):
        return
    m["abs"] = 1
    L = nt.links.new
    rough, nrm = _abs_detail(nt)
    for s in ("Roughness", "Normal"):
        for l in list(b.inputs[s].links):
            nt.links.remove(l)
    L(rough, b.inputs["Roughness"])
    L(nrm, b.inputs["Normal"])
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = BRICK["spec"]
    b.inputs["Coat Weight"].default_value = BRICK["coat"]
    b.inputs["Coat Roughness"].default_value = 0.12
    if b.inputs["Emission Strength"].default_value < 0.5 and not b.inputs["Emission Strength"].links:
        b.inputs["Emission Strength"].default_value = 0.0
    if BRICK["sss"] > 0:                    # light colours glow a little at the edges, like thin ABS
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        L(oi.outputs["Color"], bw.inputs[0])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.35, 0.85
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.0, BRICK["sss"]
        L(bw.outputs[0], mr.inputs["Value"])
        L(mr.outputs["Result"], b.inputs["Subsurface Weight"])
        b.inputs["Subsurface Scale"].default_value = 0.06


def _clear_material():
    m = bpy.data.materials.get("ClearABS")
    if m:
        return m
    m = bpy.data.materials.new("ClearABS")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    nt.links.new(oi.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.04
    b.inputs["IOR"].default_value = 1.5
    b.inputs["Specular IOR Level"].default_value = 0.6
    b.inputs["Alpha"].default_value = 0.55              # Eevee: still reads as a clear piece without refraction
    for attr, val in (("surface_render_method", "BLENDED"), ("use_raytrace_refraction", True),
                      ("thickness_mode", "SLAB")):
        if hasattr(m, attr):
            try:
                setattr(m, attr, val)
            except (TypeError, ValueError):
                pass
    m["abs"] = 1
    return m


def _brickwall_material(base, h):
    """Running-bond seams for flat brick walls (sets mark them with ob["brickwall"] = brick height in units,
    or 1 for the default 9.6 mm brick at 1 unit = 6.67 mm): the seams are dark grooves with a bump."""
    key = f"BrickWall{h:.3f}"
    m = bpy.data.materials.get(key)
    if m:
        return m
    m = base.copy()
    m.name = key
    nt = m.node_tree
    L = nt.links.new
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    col = next(l for l in nt.links if l.to_socket == b.inputs["Base Color"]).from_socket
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L(geo.outputs["Position"], sep.inputs[0])
    uu = nt.nodes.new("ShaderNodeMath"); uu.operation = "ADD"
    L(sep.outputs["X"], uu.inputs[0]); L(sep.outputs["Y"], uu.inputs[1])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    L(uu.outputs[0], comb.inputs[0]); L(sep.outputs["Z"], comb.inputs[1])
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset, br.offset_frequency = 0.5, 2
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = h * 3.33          # a 1x4 brick: 32 mm long, 9.6 mm tall
    br.inputs["Row Height"].default_value = h
    br.inputs["Mortar Size"].default_value = 0.035 * h
    br.inputs["Mortar Smooth"].default_value = 0.4
    br.inputs["Color1"].default_value = br.inputs["Color2"].default_value = (1, 1, 1, 1)
    br.inputs["Mortar"].default_value = (0.35, 0.35, 0.35, 1)
    L(comb.outputs[0], br.inputs["Vector"])
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    L(col, mul.inputs[6]); L(br.outputs["Color"], mul.inputs[7])
    L(mul.outputs[2], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    L(br.outputs["Fac"], bump.inputs["Height"])
    old = b.inputs["Normal"].links[0].from_socket if b.inputs["Normal"].links else None
    if old is not None:
        L(old, bump.inputs["Normal"])
    L(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def brick_materials():
    import re
    for m in list(bpy.data.materials):
        if m.name.startswith(SKIP_MATS) or m.name.startswith(("SetGlow", "SetGlass", "Tex_", "ClearABS",
                                                                "BrickWall")):
            continue
        _abs(m)
    clear = _clear_material()
    plain = bpy.data.materials.get("Plain")
    for ob in bpy.data.objects:
        if ob.type not in ("MESH", "CURVE", "FONT") or not ob.material_slots:
            continue
        ms = ob.material_slots[0].material
        if ob.get("clear") or (ms is not None and ms.name.startswith("SetGlass")) or \
                re.search(CLEAR_RE, ob.name):
            if ob.get("clear") == 0:
                continue
            _set_obj_mat(ob, clear)
            ob.visible_shadow = False
            continue
        if ob.get("brickwall") and plain is not None and ms is not None and ms.name == "Plain":
            v = float(ob["brickwall"])
            _set_obj_mat(ob, _brickwall_material(plain, 1.44 if v == 1 else v))
    puff = bpy.data.materials.get("Puff")
    if puff:                                   # cotton-wool smoke: matte, fluffy, no glow
        b = puff.node_tree.nodes["Principled BSDF"]
        b.inputs["Emission Strength"].default_value = 0.05
        b.inputs["Roughness"].default_value = 1.0
        b.inputs["Specular IOR Level"].default_value = 0.1
        b.inputs["Sheen Weight"].default_value = 0.8
        b.inputs["Subsurface Weight"].default_value = 0.3
        b.inputs["Alpha"].default_value = 0.9
    # printed torsos: the decal print on the plastic (same atlas as the real look)
    if plain is not None and os.path.exists(os.path.join(core.MILO, "work", "prints", "atlas.png")):
        shirt = None
        for ob in bpy.data.objects:
            if ob.type != "MESH" or not ob.name.endswith("_torso") or not ob.material_slots:
                continue
            if ob.material_slots[0].material is None or ob.material_slots[0].material.name != "Plain":
                continue
            shirt = shirt or shirt_material(plain)
            ob["shirt"] = float(_print_for(ob.name[:-6]))
            _set_obj_mat(ob, shirt)


def brick_render(sc):
    ee = sc.eevee
    for attr, val in (("use_shadows", True), ("use_raytracing", True), ("shadow_ray_count", 2),
                      ("shadow_step_count", 12), ("use_fast_gi", True), ("fast_gi_method", "GLOBAL_ILLUMINATION"),
                      ("fast_gi_distance", 3.0), ("fast_gi_ray_count", 4), ("fast_gi_step_count", 8),
                      ("use_gtao", True), ("gtao_distance", 1.0)):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except (TypeError, ValueError):
                pass
    for owner in (sc.render, ee):             # stop motion: never any motion blur
        if hasattr(owner, "use_motion_blur"):
            owner.use_motion_blur = False
    sc.render.filter_size = 1.3
    vs = sc.view_settings
    vs.view_transform = "AgX"
    try:
        vs.look = BRICK["look"]
    except TypeError:
        pass
    vs.exposure = BRICK["exposure"]
    sun = bpy.data.objects.get("Sun")
    if sun:                                   # a big soft overhead "studio" light, not a hard sun
        sun.data.energy = BRICK["sun"]
        sun.data.angle = radians(BRICK["sun_angle"])
        if hasattr(sun.data, "use_temperature"):
            sun.data.use_temperature, sun.data.temperature = True, BRICK["key_k"]
    w = sc.world
    if w:
        nt = w.node_tree
        mixs = next((n for n in nt.nodes if n.type == "MIX_SHADER"), None)
        if mixs and mixs.inputs[1].links:
            light_bg = mixs.inputs[1].links[0].from_node      # room bounce: warm-neutral, low
            light_bg.inputs["Strength"].default_value = BRICK["ambient"]
            src = light_bg.inputs["Color"].links[0].from_socket if light_bg.inputs["Color"].links else None
            mx = nt.nodes.new("ShaderNodeMix")
            mx.data_type = "RGBA"
            mx.inputs["Factor"].default_value = 0.85
            mx.inputs[7].default_value = (0.95, 0.88, 0.78, 1)
            if src is not None:
                nt.links.new(src, mx.inputs[6])
            nt.links.new(mx.outputs[2], light_bg.inputs["Color"])


def _shot_frames(shots, nf):
    starts = []
    for s in shots:
        f0 = max(0, min(nf - 1, frame(s["t0"])))
        if not starts or f0 > starts[-1][0]:
            starts.append((f0, s))
    if starts[0][0] != 0:
        starts.insert(0, (0, starts[0][1]))
    return starts


def _clear_path(sc, dg, a, b, skip):
    d = b - a
    L = d.length
    d.normalize()
    o, gone = a.copy(), 0.0
    for _ in range(16):
        ok, loc, _, _, ob, _ = sc.ray_cast(dg, o, d, distance=L - gone)
        if not ok:
            return True
        if ob is not None and ob.name not in skip and not ob.hide_render and ob.visible_shadow:
            return False
        gone = (loc - a).length + 0.01
        o = loc + d * 0.01
        if gone >= L:
            return True
    return True


def brick_lights(sc, shots, nf):
    """Tabletop softboxes, re-set for every shot like an animator's desk lights: a big key 40 deg off the lens
    and ~40 deg up on the set's side, a large dim fill from the other side, a rim from behind; distances scale
    with the subject distance and power with distance^2, so every shot gets the same light. Rays pick the
    first spot from which each light reaches the subject (walls, shelves)."""
    from mathutils import Vector, Quaternion
    import zlib
    cam = sc.camera
    if cam is None or not shots:
        return
    rigs = {"key": (_light("brick_key", "AREA", BRICK["key_k"]), BRICK["key"]),
            "fill": (_light("brick_fill", "AREA", BRICK["fill_k"]), BRICK["key"] * BRICK["fill"]),
            "rim": (_light("brick_rim", "AREA", BRICK["rim_k"]), BRICK["key"] * BRICK["rim"] * 0.5)}
    for lo, _ in rigs.values():
        lo.data.shape = "RECTANGLE"
        if hasattr(lo.data, "spread"):
            lo.data.spread = radians(120)
    chars = {o.name for o in bpy.data.objects if o.parent is not None and o.type == "MESH"}
    track = {k: [] for k in rigs}
    for f0, s in _shot_frames(shots, nf):
        sc.frame_set(f0)
        dg = bpy.context.evaluated_depsgraph_get()
        mw = cam.matrix_world
        pos, q = mw.translation.copy(), mw.to_quaternion()
        fwd, right = q @ Vector((0, 0, -1)), q @ Vector((1, 0, 0))
        dist = cam.data.dof.focus_distance if cam.data.dof.use_dof else 12.0
        dist = max(3.0, min(80.0, dist))
        P = pos + fwd * dist
        hz = Vector((-fwd.x, -fwd.y, 0))
        hz = hz.normalized() if hz.length > 1e-3 else Vector((0, -1, 0))
        side = (1, -1)[zlib.crc32(s.get("set", "x").encode()) % 2]
        R = max(7.0, 0.85 * dist)
        Z = Vector((0, 0, 1))
        plans = {"key": [(40, 40), (25, 50), (55, 35), (40, 62), (15, 70), (-40, 45)],
                 "fill": [(-55, 12), (-35, 20), (-70, 10), (-20, 30)],
                 "rim": [(160, 45), (140, 55), (180, 60), (120, 40)]}
        for k, (lo, irr) in rigs.items():
            got = None
            for az, el in plans[k]:
                hd = Quaternion(Z, radians(az * side)) @ hz
                p = P + (hd * cos(radians(el)) + Z * sin(radians(el))) * R
                if _clear_path(sc, dg, P + (p - P).normalized() * 0.5, p, chars):
                    got = p
                    break
            if got is None:
                got = P + (hz * cos(radians(70)) + Z * sin(radians(70))) * R
                e = 0.0 if k == "rim" else irr * 0.6
            else:
                e = irr
            rot = (P - got).to_track_quat("-Z", "Y").to_euler()
            size = R * BRICK["soft"] * (0.8 if k == "rim" else 1.0)
            track[k].append((f0, got, rot, e * 9.87 * R * R, size))
    for k, (lo, _) in rigs.items():
        tr = track[k]
        for i in range(3):
            core.step_keys(lo, "location", i, [(f, p[i]) for f, p, _, _, _ in tr])
            core.step_keys(lo, "rotation_euler", i, [(f, r[i]) for f, _, r, _, _ in tr])
        core.step_keys(lo.data, "energy", -1, [(f, e) for f, _, _, e, _ in tr])
        core.step_keys(lo.data, "size", -1, [(f, z) for f, _, _, _, z in tr])
        core.step_keys(lo.data, "size_y", -1, [(f, z * 0.75) for f, _, _, _, z in tr])
    # warm practicals: lamps / bulbs in the set (or anything marked ob["practical"])
    import re
    n = 0
    for ob in list(bpy.data.objects):
        if ob.type != "MESH" or n >= 10:
            continue
        if not (ob.get("practical") or re.search(r"(lamp\d*\d*$|bulb$|lampshade|_lamp_)", ob.name)):
            continue
        if re.search(r"lampb\d", ob.name) or ob.location.z < -100:
            continue
        lo = _light(ob.name + "_prac", "POINT", BRICK["practical_k"])
        sz = max(ob.dimensions) if ob.dimensions.length > 0 else 1.0
        lo.data.energy = BRICK["practical"] * max(0.5, sz) ** 2
        lo.data.shadow_soft_size = 0.4 * sz
        lo.location = ob.matrix_world.translation
        ob.visible_shadow = False
        n += 1


def brick_grade(sc):
    sc.use_nodes = True
    nt = sc.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "BLOOM"
    for k, v in (("Threshold", 0.95), ("Strength", BRICK["bloom"]), ("Size", 0.45)):
        if k in glare.inputs:
            glare.inputs[k].default_value = v
    if hasattr(glare, "quality"):
        glare.quality = "HIGH"
    cb = nt.nodes.new("CompositorNodeColorBalance")
    cb.correction_method = "LIFT_GAMMA_GAIN"
    w = BRICK["warm"]
    cb.lift = (1.0, 1.0 - w * 0.2, 1.0 - w * 0.4)        # warm toy look: amber highlights, neutral darks
    cb.gain = (1.0 + w, 1.0 + w * 0.2, 1.0 - w * 1.2)
    hsv = nt.nodes.new("CompositorNodeHueSat")
    hsv.inputs["Saturation"].default_value = BRICK["sat"]
    bc = nt.nodes.new("CompositorNodeBrightContrast")
    bc.inputs["Contrast"].default_value = BRICK["contrast"]
    comp = nt.nodes.new("CompositorNodeComposite")
    L = nt.links.new
    L(rl.outputs["Image"], glare.inputs["Image"]); L(glare.outputs["Image"], cb.inputs["Image"])
    L(cb.outputs["Image"], hsv.inputs["Image"]); L(hsv.outputs["Image"], bc.inputs["Image"])
    L(bc.outputs["Image"], comp.inputs["Image"])


# ---- the stop-motion pass
def _fcurves_of(idb):
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return None, []
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        return (ad.action.name, getattr(ad.action_slot, "handle", 0)), list(cb.fcurves) if cb else []
    except Exception:
        return (ad.action.name, 0), list(ad.action.fcurves)


def _anim_ids():
    out = []
    for coll in (bpy.data.objects, bpy.data.cameras, bpy.data.lights, bpy.data.materials, bpy.data.worlds,
                 bpy.data.scenes, bpy.data.meshes, bpy.data.curves, bpy.data.node_groups, bpy.data.shape_keys):
        for idb in coll:
            for x in (idb, getattr(idb, "node_tree", None)):
                if x is not None and x.animation_data is not None and x.animation_data.action is not None:
                    out.append(x)
    return out


def hold_schedule(shots, nf):
    """src[f] = the frame whose pose frame f shows. Holds restart at every cut (a new camera set-up), 2 frames
    each (BRICK["hold"]), 3 on slow beats (BRICK["threes"])."""
    import numpy as np_
    src = np_.arange(nf)
    st = _shot_frames(shots, nf)
    for i, (f0, s) in enumerate(st):
        f1 = st[i + 1][0] if i + 1 < len(st) else nf
        L = 3 if s.get("beat") in BRICK["threes"] else int(BRICK["hold"])
        g = np_.arange(f0, f1)
        src[f0:f1] = f0 + ((g - f0) // max(1, L)) * max(1, L)
    return src


def stop_motion(sc, shots, nf):
    """Hold every animated channel on twos (threes on slow beats), restart the holds at every cut, add a hand-
    placed error per pose to moving objects (frozen while an object rests), and flicker the exposure."""
    import numpy as np_
    import zlib
    t0 = __import__("time").time()
    src = hold_schedule(shots, nf)
    hstart, hid = np_.unique(src, return_inverse=True)
    H = len(hstart)
    cam = sc.camera
    jp, jr = BRICK["jit_pos"], radians(BRICK["jit_rot"])
    seen, n_fc, n_jit, mv = set(), 0, 0, []
    for idb in _anim_ids():
        key, fcs = _fcurves_of(idb)
        if key in seen or not fcs:
            continue
        seen.add(key)
        stepped = []
        for fc in fcs:
            kp = fc.keyframe_points
            n = len(kp)
            if n == 0:
                continue
            co = np_.empty(2 * n, np_.float64)
            kp.foreach_get("co", co)
            co = co.reshape(-1, 2)
            ip = np_.empty(n, np_.int32)
            kp.foreach_get("interpolation", ip)
            if (ip != 0).any() or len(fc.modifiers):
                vals = np_.array([fc.evaluate(float(f)) for f in src])
            else:
                F = np_.round(co[:, 0]).astype(np_.int64)
                order = np_.argsort(F, kind="stable")
                F, V = F[order], co[order, 1]
                idx = np_.searchsorted(F, src, side="right") - 1
                vals = V[np_.clip(idx, 0, n - 1)]
            stepped.append((fc, vals))
        # hand-placed error on moving objects (characters, props): position on x/y, rotation on every axis
        is_obj = isinstance(idb, bpy.types.Object)
        if is_obj and idb.type not in ("LIGHT",) and not idb.name.startswith(("puff", "pollen", "mote", "brick_")):
            camera = idb == cam
            apos = 0.0 if camera else jp * max(idb.matrix_world.to_scale())
            arot = radians(BRICK["cam_jit"]) if camera else jr
            moving = np_.zeros(H, bool)
            moving[0] = True
            for fc, vals in stepped:
                hv = vals[hstart]
                if fc.data_path == "location":
                    thr = BRICK["move_pos"] * max(0.2, max(idb.matrix_world.to_scale()))
                elif fc.data_path == "rotation_euler":
                    thr = radians(BRICK["move_rot"])
                else:
                    continue
                moving[1:] |= np_.abs(np_.diff(hv)) > thr
            cnt = np_.cumsum(moving) - 1
            mv.append(moving.mean())
            for fc, vals in stepped:
                if fc.data_path == "location" and fc.array_index < 2:
                    amp = apos
                elif fc.data_path == "rotation_euler":
                    amp = arot
                else:
                    continue
                if amp <= 0:
                    continue
                seed = zlib.crc32(f"{idb.name}|{fc.data_path}|{fc.array_index}".encode())
                draws = np_.random.default_rng(seed).uniform(-1, 1, H) * amp
                vals += draws[cnt][hid]
                n_jit += 1
        for fc, vals in stepped:
            keep = np_.concatenate(([0], np_.nonzero(vals[1:] != vals[:-1])[0] + 1))
            kp = fc.keyframe_points
            kp.clear()
            kp.add(len(keep))
            kp.foreach_set("co", np_.column_stack((keep.astype(np_.float64), vals[keep])).ravel())
            kp.foreach_set("interpolation", np_.zeros(len(keep), np_.int32))
            fc.update()
            n_fc += 1
    # exposure flicker: a new tiny exposure every held frame, like a real camera between photos
    if BRICK["flicker"] > 0:
        rng = np_.random.default_rng(7)
        ev = BRICK["exposure"] + rng.uniform(-1, 1, H) * BRICK["flicker"]
        keys(sc, "view_settings.exposure", -1, [int(f) for f in hstart], [float(v) for v in ev])
    print(f"[brick] stop motion: {n_fc} channels held {nf / H:.2f} frames per pose ({H} poses / {nf} frames), "
          f"{n_jit} jittered (objects re-placed on {100 * (sum(mv) / max(1, len(mv))):.1f}% of poses on average, max {100 * max(mv or [0]):.0f}%), "
          f"flicker +-{BRICK['flicker']} EV ({__import__('time').time() - t0:.1f}s)")


def brick_foley(shots, nf):
    """work/<ep>/foley.json for post.py: a plastic clack on every footstep (on the held frame it lands on),
    a run of brick snaps on every transformation."""
    import json
    src = hold_schedule(shots, nf)
    snap = lambda t: float(src[max(0, min(nf - 1, frame(t)))]) / core.FPS
    steps, snaps = set(), set()
    for ch in getattr(core.Char, "ALL", []):
        if getattr(ch, "crowd", False):
            continue
        for start, kind, d in getattr(ch, "moves", []):
            if kind != "run" or d[2] == "flail":
                continue
            t = start + 0.1
            while t < d[0]:
                steps.add(round(snap(t), 3))
                t += 1 / (2 * 2.6)
        for t, _ in getattr(ch, "wears", []):
            if t > 0:
                for i in range(5):
                    snaps.add(round(snap(t + 0.07 * i), 3))
    out = os.path.join(core.MILO, "work", os.environ.get("MILO_EP", "ep01"), "foley.json")
    try:
        with open(out, "w") as f:
            json.dump({"steps": sorted(steps), "snaps": sorted(snaps)}, f)
        print(f"[brick] foley: {len(steps)} steps, {len(snaps)} snaps -> {out}")
    except OSError as e:
        print("[brick] foley not written:", e)


def apply(look, C, sc, nf, shots=None):
    if look == "base":
        return
    if look == "brick":
        brick_render(sc)
        brick_materials()
        brick_grade(sc)
        pendant(C, nf)
        if shots:
            brick_lights(sc, shots, nf)
            stop_motion(sc, shots, nf)
            if BRICK["foley"]:
                brick_foley(shots, nf)
        return
    if look == "real":
        real_render(sc)
        room_lights()
        front_walls()
        puff = bpy.data.materials.get("Puff")
        if puff:                                   # puffs read as soft smoke, not a flat white blowout
            b = puff.node_tree.nodes["Principled BSDF"]
            b.inputs["Emission Strength"].default_value = 0.3
        plastic()
        texture_world()
        dress()
        real_grade(sc)
        pendant(C, nf)
        return
    toon(grade_shadows=(look == "brand"))
    if look == "brand":
        grade(sc)
        pendant(C, nf)
