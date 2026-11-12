# Cryptext : construction de la scène (glyphes 3D, nuage de points, réseau Geometry Nodes, lumière, caméra).
import bpy, math, os
import numpy as np
from mathutils import Matrix, Vector

FONT_DEFAULT = os.path.join(os.path.dirname(__file__), "fonts", "Cryptext25-Regular.ttf")
DIGITS = "0123456789"
TREE = "Cryptext Animation"
OBJ = "Cryptext"
GLYPH_COLL = "Cryptext glyphes"
MAT = "Cryptext matière"
CAM_DIST = 12.0                    # distance caméra → plan du nombre (m)


# ------------------------------------------------------------------ helpers nodes
def sock(node, key, out=False):
    coll = node.outputs if out else node.inputs
    if isinstance(key, int):
        return coll[key]
    for s in coll:
        if s.name == key and s.enabled:
            return s
    for s in coll:
        if s.identifier == key:
            return s
    raise KeyError(f"{node.bl_idname}: {key}")


class B:
    def __init__(s, tree):
        s.n, s.l = tree.nodes, tree.links

    def set(s, dst, v):
        if isinstance(v, bpy.types.NodeSocket):
            s.l.new(v, dst)
        elif v is not None:
            dst.default_value = v

    def node(s, typ, ins=None, **props):
        nd = s.n.new(typ)
        for k, v in props.items():
            setattr(nd, k, v)
        for k, v in (ins or {}).items():
            s.set(sock(nd, k), v)
        return nd

    def out(s, nd, key=0):
        return sock(nd, key, out=True)

    def m(s, op, a, b=0.0, c=0.0, clamp=False):
        nd = s.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        s.set(nd.inputs[0], a); s.set(nd.inputs[1], b); s.set(nd.inputs[2], c)
        return nd.outputs[0]

    def v(s, op, a, b=None, scale=None):
        nd = s.node('ShaderNodeVectorMath', operation=op)
        s.set(nd.inputs[0], a)
        if b is not None:
            s.set(nd.inputs[1], b)
        if scale is not None:
            s.set(sock(nd, 'Scale'), scale)
        return nd.outputs[0]

    def vs(s, a, f):                      # vecteur × scalaire
        return s.v('SCALE', a, scale=f)

    def remap(s, x, a, b, c=0.0, d=1.0, interp='LINEAR'):
        nd = s.node('ShaderNodeMapRange', {'Value': x, 'From Min': a, 'From Max': b,
                                           'To Min': c, 'To Max': d},
                    data_type='FLOAT', interpolation_type=interp)
        nd.clamp = True
        return s.out(nd, 'Result')

    def combine(s, x=0.0, y=0.0, z=0.0):
        return s.out(s.node('ShaderNodeCombineXYZ', {'X': x, 'Y': y, 'Z': z}))

    def attr(s, name, dtype):
        return s.out(s.node('GeometryNodeInputNamedAttribute', {'Name': name}, data_type=dtype), 'Attribute')

    def noise(s, vec, w, scale):
        """Bruit 4D centré sur 0, amplitude ~[-1, 1] par composante."""
        nd = s.node('ShaderNodeTexNoise', {'Vector': vec, 'W': w, 'Scale': scale, 'Detail': 1.0,
                                           'Roughness': 0.5}, noise_dimensions='4D')
        return s.vs(s.v('SUBTRACT', s.out(nd, 'Color'), (0.5, 0.5, 0.5)), 4.0)

    def euler(s, vec):
        return s.out(s.node('FunctionNodeEulerToRotation', {'Euler': vec}))


# ------------------------------------------------------------------ paramètres animables (entrées du modificateur)
# (nom, type, défaut, min, max, sous-type)
PANELS = [
    ("Apparition", [
        ("Début apparition", 'FLOAT', 0.0, 0.0, 600.0, 'TIME_ABSOLUTE'),
        ("Étalement apparition", 'FLOAT', 14.0, 0.0, 600.0, 'TIME_ABSOLUTE'),
        ("Durée du fondu", 'FLOAT', 6.0, 0.01, 120.0, 'TIME_ABSOLUTE'),
        ("Profondeur d'arrivée", 'FLOAT', 3.0, 0.0, 50.0, 'DISTANCE'),
    ]),
    ("Flottement", [
        ("Amplitude flottement", 'FLOAT', 0.45, 0.0, 10.0, 'DISTANCE'),
        ("Rotation flottement", 'FLOAT', 25.0, 0.0, 360.0, 'NONE'),
        ("Vitesse flottement", 'FLOAT', 0.07, 0.0, 5.0, 'NONE'),
        ("Échelle du bruit", 'FLOAT', 0.2, 0.0, 10.0, 'NONE'),
        ("Immobile à", 'FLOAT', 30.0, 0.0, 600.0, 'TIME_ABSOLUTE'),
        ("Durée d'immobilisation", 'FLOAT', 14.0, 0.01, 600.0, 'TIME_ABSOLUTE'),
        ("Inclinaison au repos", 'FLOAT', 10.0, 0.0, 90.0, 'NONE'),
    ]),
    ("Agitation", [
        ("Début agitation", 'FLOAT', 31.0, 0.0, 600.0, 'TIME_ABSOLUTE'),
        ("Montée agitation", 'FLOAT', 1.5, 0.01, 60.0, 'TIME_ABSOLUTE'),
        ("Amplitude agitation", 'FLOAT', 0.12, 0.0, 5.0, 'DISTANCE'),
        ("Rotation agitation", 'FLOAT', 14.0, 0.0, 180.0, 'NONE'),
        ("Vitesse agitation", 'FLOAT', 2.5, 0.0, 50.0, 'NONE'),
    ]),
    ("Nombre", [
        ("Taille dans la foule", 'FLOAT', 0.55, 0.05, 1.0, 'FACTOR'),
        ("Agitation du nombre", 'FLOAT', 0.4, 0.0, 2.0, 'FACTOR'),
        ("Croissance", 'FLOAT', 4.0, 0.01, 60.0, 'TIME_ABSOLUTE'),
    ]),
    ("Répulsion", [
        ("Début répulsion", 'FLOAT', 33.0, 0.0, 600.0, 'TIME_ABSOLUTE'),
        ("Durée répulsion", 'FLOAT', 3.5, 0.01, 60.0, 'TIME_ABSOLUTE'),
        ("Étalement répulsion", 'FLOAT', 2.0, 0.0, 60.0, 'TIME_ABSOLUTE'),
        ("Distance répulsion", 'FLOAT', 16.0, 0.0, 200.0, 'DISTANCE'),
        ("Vrille de sortie", 'FLOAT', 240.0, 0.0, 3600.0, 'NONE'),
    ]),
    ("Pivot", [
        ("Début pivot", 'FLOAT', 41.0, 0.0, 600.0, 'TIME_ABSOLUTE'),
        ("Durée pivot", 'FLOAT', 3.0, 0.01, 60.0, 'TIME_ABSOLUTE'),
        ("Mode pivot", 'INT', 0, 0, 2, 'NONE'),
    ]),
    ("Cercle", [
        ("Rayon utile", 'FLOAT', 0.97, 0.1, 1.5, 'FACTOR'),
        ("Fondu au bord", 'FLOAT', 0.14, 0.001, 1.0, 'FACTOR'),
        ("Zone ronde", 'BOOL', True, 0, 1, 'NONE'),
        ("Demi-champ", 'FLOAT', 0.36, 0.01, 10.0, 'NONE'),
    ]),
]
HIDDEN = {"Zone ronde", "Demi-champ", "Rayon utile"}      # pilotés par l'add-on, pas affichés dans les panneaux de timing
HOLD_AFTER = 4.0          # secondes gardées après le pivot pour la durée de la scène
PIVOT_MODES = ("Axe X (lecture retournée)", "Axe X + axe vertical", "Dans le plan de l'image")


def build_tree(glyph_coll):
    if TREE in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[TREE])
    tree = bpy.data.node_groups.new(TREE, 'GeometryNodeTree')
    tree.is_modifier = True
    itf = tree.interface
    itf.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    itf.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    for pname, items in PANELS:
        panel = itf.new_panel(pname)
        for name, typ, dflt, mn, mx, sub in items:
            st = {'FLOAT': 'NodeSocketFloat', 'INT': 'NodeSocketInt', 'BOOL': 'NodeSocketBool'}[typ]
            s = itf.new_socket(name, in_out='INPUT', socket_type=st, parent=panel)
            s.default_value = dflt
            if typ != 'BOOL':
                s.min_value, s.max_value = mn, mx
            if typ == 'FLOAT' and sub != 'NONE':
                s.subtype = sub

    b = B(tree)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    I = lambda name: b.out(gi, name)
    rad = lambda x: b.m('MULTIPLY', x, math.pi / 180)

    t = b.out(b.node('GeometryNodeInputSceneTime'), 'Seconds')
    p0 = b.out(b.node('GeometryNodeInputPosition'))
    seed = b.attr("graine", 'FLOAT')
    final = b.attr("final", 'FLOAT')               # 1 = chiffre du nombre final
    cloud = b.m('SUBTRACT', 1.0, final)
    r_fade = b.attr("r_apparition", 'FLOAT')
    r_rep = b.attr("r_repulsion", 'FLOAT')
    direction = b.attr("direction", 'FLOAT_VECTOR')
    spin = b.attr("vrille", 'FLOAT_VECTOR')
    tilt = b.attr("inclinaison", 'FLOAT_VECTOR')

    # --- apparition depuis le noir (+ arrivée depuis le fond)
    f0 = b.m('MULTIPLY_ADD', r_fade, I("Étalement apparition"), I("Début apparition"))
    fade = b.remap(t, f0, b.m('ADD', f0, I("Durée du fondu")), interp='SMOOTHSTEP')
    arrive_t = b.remap(t, f0, b.m('ADD', f0, b.m('MULTIPLY', I("Durée du fondu"), 1.6)), interp='SMOOTHERSTEP')
    arrive = b.combine(y=b.m('MULTIPLY', b.m('SUBTRACT', 1.0, arrive_t), I("Profondeur d'arrivée")))

    # --- flottement qui s'éteint jusqu'à l'immobilité
    calm0 = b.m('SUBTRACT', I("Immobile à"), I("Durée d'immobilisation"))
    float_env = b.remap(t, calm0, I("Immobile à"), 1.0, 0.0, interp='SMOOTHERSTEP')
    w_float = b.m('MULTIPLY_ADD', t, I("Vitesse flottement"), seed)
    float_off = b.vs(b.noise(p0, w_float, I("Échelle du bruit")), b.m('MULTIPLY', I("Amplitude flottement"), float_env))
    float_rot = b.vs(b.noise(b.v('ADD', p0, (17.3, 5.1, -9.7)), w_float, I("Échelle du bruit")),
                     b.m('MULTIPLY', rad(I("Rotation flottement")), float_env))

    # --- agitation (le nombre s'agite moins et se calme à la fin de la répulsion)
    rep_end = b.m('ADD', b.m('ADD', I("Début répulsion"), I("Durée répulsion")), I("Étalement répulsion"))
    ag_env = b.remap(t, I("Début agitation"), b.m('ADD', I("Début agitation"), I("Montée agitation")), interp='SMOOTHSTEP')
    num_calm = b.remap(t, b.m('SUBTRACT', rep_end, 1.0), b.m('ADD', rep_end, 0.5), 1.0, 0.0, interp='SMOOTHSTEP')
    ag_k = b.m('ADD', cloud, b.m('MULTIPLY', final, b.m('MULTIPLY', I("Agitation du nombre"), num_calm)))
    ag_env = b.m('MULTIPLY', ag_env, ag_k)
    w_ag = b.m('MULTIPLY_ADD', t, I("Vitesse agitation"), b.m('MULTIPLY', seed, 3.7))
    ag_off = b.vs(b.noise(p0, w_ag, 3.0), b.m('MULTIPLY', I("Amplitude agitation"), ag_env))
    ag_rot = b.vs(b.noise(b.v('ADD', p0, (-31.0, 8.0, 2.0)), w_ag, 3.0),
                  b.m('MULTIPLY', rad(I("Rotation agitation")), ag_env))

    # --- répulsion hors de l'image (accélération)
    r0 = b.m('MULTIPLY_ADD', r_rep, I("Étalement répulsion"), I("Début répulsion"))
    rprog = b.remap(t, r0, b.m('ADD', r0, I("Durée répulsion")))
    push = b.m('MULTIPLY', b.m('MULTIPLY', b.m('POWER', rprog, 2.2), I("Distance répulsion")), cloud)
    rep_off = b.vs(direction, push)
    rep_rot = b.vs(spin, b.m('MULTIPLY', b.m('MULTIPLY', rprog, rad(I("Vrille de sortie"))), cloud))

    # le nombre est plus petit dans la foule et grandit pendant la répulsion
    grow = b.remap(t, I("Début répulsion"), b.m('ADD', I("Début répulsion"), I("Croissance")), interp='SMOOTHERSTEP')
    nsc = b.m('ADD', I("Taille dans la foule"), b.m('MULTIPLY', grow, b.m('SUBTRACT', 1.0, I("Taille dans la foule"))))
    sc = b.m('ADD', 1.0, b.m('MULTIPLY', final, b.m('SUBTRACT', nsc, 1.0)))
    pos = b.v('ADD', b.vs(p0, sc), b.v('ADD', float_off, b.v('ADD', ag_off, arrive)))
    pos = b.v('ADD', pos, rep_off)
    rest = b.vs(tilt, b.m('MULTIPLY', rad(I("Inclinaison au repos")), cloud))
    rot = b.v('ADD', b.v('ADD', rest, float_rot), b.v('ADD', ag_rot, rep_rot))

    # --- zone ronde (hélice holographique) : tout s'éteint avant de toucher le bord du cercle inscrit
    sep = b.node('ShaderNodeSeparateXYZ', {'Vector': pos})
    persp = b.m('MULTIPLY', b.m('MAXIMUM', b.m('ADD', b.out(sep, 'Y'), CAM_DIST), 0.01), I("Demi-champ"))
    ln = b.node('ShaderNodeVectorMath', operation='LENGTH')
    b.set(ln.inputs[0], b.combine(x=b.out(sep, 'X'), z=b.out(sep, 'Z')))
    r_scr = b.m('DIVIDE', b.out(ln, 'Value'), persp)
    ext = b.m('DIVIDE', b.m('MULTIPLY', b.attr("taille", 'FLOAT'), b.m('MULTIPLY', sc, 0.55)), persp)
    edge = b.remap(b.m('ADD', r_scr, ext), b.m('SUBTRACT', I("Rayon utile"), I("Fondu au bord")), I("Rayon utile"),
                   1.0, 0.0, interp='SMOOTHSTEP')
    use = b.m('MULTIPLY', I("Zone ronde"), 1.0)
    fade = b.m('MULTIPLY', fade, b.m('ADD', b.m('MULTIPLY', use, b.m('SUBTRACT', edge, 1.0)), 1.0))

    pts = b.out(b.node('GeometryNodeMeshToPoints', {'Mesh': I("Geometry")}))
    pts = b.out(b.node('GeometryNodeStoreNamedAttribute', {'Geometry': pts, 'Name': "fondu", 'Value': fade},
                       data_type='FLOAT', domain='POINT'))
    pts = b.out(b.node('GeometryNodeSetPosition', {'Geometry': pts, 'Position': pos}))

    ci = b.node('GeometryNodeCollectionInfo', {'Separate Children': True, 'Reset Children': True},
                transform_space='RELATIVE')
    sock(ci, 'Collection').default_value = glyph_coll
    inst = b.node('GeometryNodeInstanceOnPoints', {
        'Points': pts, 'Instance': b.out(ci), 'Pick Instance': True,
        'Instance Index': b.attr("glyphe", 'INT'), 'Rotation': b.euler(rot),
        'Scale': b.m('MULTIPLY', b.attr("taille", 'FLOAT'), sc)})
    geo = b.out(inst)

    # --- pivot du nombre final autour de son centre (origine)
    th = b.m('MULTIPLY', b.remap(t, I("Début pivot"), b.m('ADD', I("Début pivot"), I("Durée pivot")),
                                 interp='SMOOTHERSTEP'), math.pi)
    past = b.m('GREATER_THAN', th, math.pi / 2)
    th_fold = b.m('SUBTRACT', th, b.m('MULTIPLY', past, b.m('SUBTRACT', b.m('MULTIPLY', th, 2.0), math.pi)))
    ident = b.euler((0.0, 0.0, 0.0))
    first = [b.euler(b.combine(x=th_fold)), b.euler(b.combine(x=th)), ident]
    second = [b.euler(b.combine(y=b.m('MULTIPLY', past, math.pi))), b.euler(b.combine(z=th)),
              b.euler(b.combine(y=th))]
    sel = b.m('GREATER_THAN', final, 0.5)
    for rots in (first, second):
        sw = b.node('GeometryNodeIndexSwitch', data_type='ROTATION')
        sw.index_switch_items.new()
        b.set(sock(sw, 'Index'), I("Mode pivot"))
        for k, r in enumerate(rots):
            b.l.new(r, sw.inputs[k + 1])
        geo = b.out(b.node('GeometryNodeRotateInstances', {
            'Instances': geo, 'Selection': sel, 'Rotation': b.out(sw), 'Pivot Point': (0.0, 0.0, 0.0),
            'Local Space': False}))
    b.l.new(geo, go.inputs[0])
    return tree


# ------------------------------------------------------------------ matière
MATERIALS = {   # couleur, métal, rugosité
    'GOLD': ((1.0, 0.58, 0.16), 1.0, 0.18),
    'SILVER': ((0.96, 0.95, 0.93), 1.0, 0.2),
    'WHITE': ((0.92, 0.92, 0.92), 0.0, 0.45),
}


def get_material():
    mat = bpy.data.materials.get(MAT)
    if mat:
        return mat
    mat = bpy.data.materials.new(MAT)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (500, 0)
    mix = nt.nodes.new('ShaderNodeMixShader'); mix.location = (300, 0)
    black = nt.nodes.new('ShaderNodeEmission'); black.location = (0, 150)
    black.inputs['Color'].default_value = (0, 0, 0, 1); black.inputs['Strength'].default_value = 0
    p = nt.nodes.new('ShaderNodeBsdfPrincipled'); p.name = "Surface"; p.location = (0, -100)
    fa = nt.nodes.new('ShaderNodeAttribute'); fa.location = (0, 350)
    fa.attribute_type, fa.attribute_name = 'INSTANCER', "fondu"
    nt.links.new(fa.outputs['Fac'], mix.inputs[0])
    nt.links.new(black.outputs[0], mix.inputs[1])
    nt.links.new(p.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def apply_material_preset(preset, roughness=None):
    mat = get_material()
    p = mat.node_tree.nodes["Surface"]
    col, metal, rough = MATERIALS[preset]
    p.inputs['Base Color'].default_value = (*col, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough if roughness is None else roughness


# ------------------------------------------------------------------ glyphes
def load_font(path):
    path = bpy.path.abspath(path) if path else FONT_DEFAULT
    for f in bpy.data.fonts:
        if bpy.path.abspath(f.filepath) == path:
            return f
    return bpy.data.fonts.load(path)


def _text_curve(font, body, extrude, bevel):
    cu = bpy.data.curves.new("_cryptext_tmp", 'FONT')
    cu.font, cu.body, cu.size = font, body, 1.0
    cu.align_x, cu.align_y = 'LEFT', 'TOP_BASELINE'
    cu.extrude, cu.bevel_depth, cu.bevel_resolution = extrude, bevel, 3
    cu.resolution_u = 6
    cu.offset = -bevel * 0.5            # garde l'épaisseur du trait malgré le biseau
    return cu


def _to_mesh(cu, name):
    ob = bpy.data.objects.new("_cryptext_tmp", cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    me.name = name
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    return me


def _mesh_xy(me):
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)


def glyph_chars(number):
    extra = sorted({c for c in number if not c.isspace() and c not in DIGITS})
    return DIGITS + "".join(extra)


def build_glyphs(font, chars, extrude, bevel):
    """Un objet maillé par caractère, centré sur sa boîte, dans une collection hors scène."""
    coll = bpy.data.collections.get(GLYPH_COLL) or bpy.data.collections.new(GLYPH_COLL)
    for ob in list(coll.objects):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)
    mat = get_material()
    centers = {}
    for k, ch in enumerate(chars):
        me = _to_mesh(_text_curve(font, ch, extrude, bevel), f"glyphe {ch}")
        co = _mesh_xy(me)
        c = (co.min(0) + co.max(0)) / 2 if len(co) else np.zeros(3)
        c[2] = 0.0                       # profondeur : on garde l'extrusion centrée
        co -= c
        me.vertices.foreach_set('co', co.ravel())
        # le texte est dans le plan XY ; on le redresse face caméra (plan XZ, caméra en -Y)
        me.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))
        me.materials.clear(); me.materials.append(mat)
        for poly in me.polygons:
            poly.use_smooth = True
        ob = bpy.data.objects.new(f"g{k:03d}_{ch}", me)
        coll.objects.link(ob)
        centers[ch] = c
    return coll, centers


def layout_number(font, number, extrude, bevel):
    """Centre (x, z) de chaque caractère non blanc du nombre, en unités de taille 1, nombre centré."""
    idx = [i for i, c in enumerate(number) if not c.isspace()]
    if not idx:
        return [], 1.0, 1.0
    cu = _text_curve(font, number, extrude, bevel)
    for k in range(len(idx) + 1):
        cu.materials.append(None)
    for k, i in enumerate(idx):
        cu.body_format[i].material_index = k + 1
    me = _to_mesh(cu, "_cryptext_layout")
    co = _mesh_xy(me)
    mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('material_index', mi)
    res = []
    for k in range(len(idx)):
        vs = {v for p in me.polygons if p.material_index == k + 1 for v in p.vertices}
        pts = co[list(vs)] if vs else np.zeros((1, 3))
        res.append(((pts.min(0) + pts.max(0)) / 2, (pts.max(0) - pts.min(0)) / 2))
    lo, hi = co.min(0), co.max(0)
    bpy.data.meshes.remove(me)
    mid = (lo + hi) / 2
    out = [(number[i], float(c[0] - mid[0]), float(c[1] - mid[1]), float(e[0]), float(e[1]))
           for i, (c, e) in zip(idx, res)]
    return out, float(hi[0] - lo[0]), float(hi[1] - lo[1])


# ------------------------------------------------------------------ nuage de points
def frame_half_width(cam_data):
    return CAM_DIST * (cam_data.sensor_width / 2) / cam_data.lens


def build_points(st, centers_unused=None, font=None):
    """Positions de repos + attributs : chiffres du nuage et chiffres du nombre final."""
    font = font or load_font(st.font_path)
    cam = bpy.data.objects.get("Cryptext caméra")
    hw = frame_half_width(cam.data) if cam else frame_half_width(bpy.data.cameras.new("_tmp"))
    chars = glyph_chars(st.number)
    gidx = {c: i for i, c in enumerate(chars)}
    lay, w, h = layout_number(font, st.number, st.extrude, st.bevel)
    nsize = st.number_width * 2 * hw / max(w, 1e-3)
    # réglages par caractère (décalages) + espacement, puis recentrage
    offs = list(st.chars)
    n_ch = len(lay)
    pl = []
    for k, (c, x, z, ex, ez) in enumerate(lay):
        ox, oz = (offs[k].x, offs[k].z) if k < len(offs) else (0.0, 0.0)
        pl.append([c, x + ox + (k - (n_ch - 1) / 2) * st.spacing, z + oz, ex, ez])
    if pl:
        a = np.array([[q[1] - q[3], q[1] + q[3], q[2] - q[4], q[2] + q[4]] for q in pl])
        cx, cz = (a[:, 0].min() + a[:, 1].max()) / 2, (a[:, 2].min() + a[:, 3].max()) / 2
        for q in pl:
            q[1] -= cx; q[2] -= cz
        w, h = a[:, 1].max() - a[:, 0].min(), a[:, 3].max() - a[:, 2].min()
    lay = [(q[0], q[1], q[2]) for q in pl]
    # zone ronde : le nombre (et sa rotation) doit tenir dans le cercle, perspective comprise
    limited = False
    if st.circle and pl:
        rmax = max(math.hypot(abs(q[1]) + q[3], abs(q[2]) + q[4]) for q in pl)
        # pire cas : un coin bascule vers la caméra d'une distance égale à son rayon
        R = st.circle_radius * hw * 0.98
        lim = R * CAM_DIST / (CAM_DIST + R) / rmax
        if nsize > lim:
            nsize, limited = lim, True

    rng = np.random.default_rng(st.seed)
    # boîte du nombre à l'écran (pour le dégager des chiffres trop proches en profondeur)
    bx, bz = w * nsize / 2 + st.clearance, h * nsize / 2 + st.clearance

    # échantillonnage « meilleur candidat » dans le volume vu par la caméra (pas d'amas)
    n = st.count
    y_lo, y_hi = -st.depth_front, st.depth_back
    P = np.zeros((0, 3))
    S = np.zeros((0, 3))                       # coordonnées normalisées (écran x, écran z, profondeur)
    k_cand = 10
    for i in range(n):
        y = rng.uniform(y_lo, y_hi, k_cand)
        sc = (CAM_DIST + y) / CAM_DIST * hw * st.spread
        if st.circle:                            # disque : le nuage épouse le cercle
            rr, aa = np.sqrt(rng.random(k_cand)) * st.circle_radius, rng.uniform(0, 2 * np.pi, k_cand)
            sx, sz = rr * np.cos(aa), rr * np.sin(aa)
        else:
            sx, sz = rng.uniform(-1, 1, k_cand), rng.uniform(-1, 1, k_cand)
        cand = np.stack([sx * sc, y, sz * sc], 1)
        ok = ~((np.abs(sx * sc * CAM_DIST / (CAM_DIST + y)) < bx) &
               (np.abs(sz * sc * CAM_DIST / (CAM_DIST + y)) < bz) & (np.abs(y) < st.clearance + 0.3))
        if not ok.any():
            continue
        cand, cs = cand[ok], np.stack([sx, sz, (y - y_lo) / max(y_hi - y_lo, 1e-3) * 0.6], 1)[ok]
        if len(S):
            d = ((cs[:, None, :] - S[None, :, :]) ** 2).sum(-1).min(1)
            j = int(d.argmax())
        else:
            j = 0
        P = np.vstack([P, cand[j]]); S = np.vstack([S, cs[j]])
    m = len(P)

    size = rng.uniform(st.size_min, st.size_max, m) * nsize
    glyph = rng.integers(0, 10, m)
    # direction de répulsion : s'éloigne du centre de l'image (le nombre), un peu de dispersion
    screen = P[:, [0, 2]] / ((CAM_DIST + P[:, 1]) / CAM_DIST)[:, None]
    ang = np.arctan2(screen[:, 1], screen[:, 0]) + rng.normal(0, 0.25, m)
    rnd = rng.uniform(0, 2 * np.pi, m)
    near = np.hypot(*screen.T) < 0.2
    ang[near] = rnd[near]
    dirs = np.stack([np.cos(ang), rng.normal(0, 0.25, m) - 0.15, np.sin(ang)], 1)
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    spin = rng.normal(0, 1, (m, 3)); spin /= np.linalg.norm(spin, axis=1, keepdims=True)
    tilt = rng.uniform(-1, 1, (m, 3)) * np.array([1.0, 0.6, 1.0])
    r_app = rng.random(m)
    r_rep = rng.random(m)

    # chiffres du nombre final
    nf = len(lay)
    FP = np.array([[x * nsize, 0.0, z * nsize] for _, x, z in lay]).reshape(-1, 3)
    pos = np.vstack([P, FP])
    final = np.r_[np.zeros(m), np.ones(nf)]
    glyph = np.r_[glyph, [gidx[c] for c, _, _ in lay]].astype(np.int32)
    size = np.r_[size, np.full(nf, nsize)]
    dirs = np.vstack([dirs, np.zeros((nf, 3))])
    spin = np.vstack([spin, np.zeros((nf, 3))])
    tilt = np.vstack([tilt, np.zeros((nf, 3))])
    r_app = np.r_[r_app, rng.random(nf) * 0.5 + 0.5]       # le nombre n'arrive pas en premier
    r_rep = np.r_[r_rep, np.zeros(nf)]
    graine = rng.uniform(0, 100, m + nf)
    st["_limited"] = limited

    ob = bpy.data.objects.get(OBJ)
    me = bpy.data.meshes.new("Cryptext points")
    me.vertices.add(len(pos))
    me.vertices.foreach_set('co', pos.astype(np.float32).ravel())
    for name, typ, data in (("final", 'FLOAT', final), ("glyphe", 'INT', glyph), ("taille", 'FLOAT', size),
                            ("direction", 'FLOAT_VECTOR', dirs), ("vrille", 'FLOAT_VECTOR', spin),
                            ("inclinaison", 'FLOAT_VECTOR', tilt), ("r_apparition", 'FLOAT', r_app),
                            ("r_repulsion", 'FLOAT', r_rep), ("graine", 'FLOAT', graine)):
        a = me.attributes.new(name, typ, 'POINT')
        key = 'vector' if typ == 'FLOAT_VECTOR' else 'value'
        a.data.foreach_set(key, data.astype(np.int32 if typ == 'INT' else np.float32).ravel())
    if ob:
        old = ob.data
        ob.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
    return me, m, nf


# ------------------------------------------------------------------ scène
def setup_world(scene):
    w = bpy.data.worlds.get("Cryptext monde") or bpy.data.worlds.new("Cryptext monde")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld'); out.location = (800, 0)
    mix = nt.nodes.new('ShaderNodeMixShader'); mix.location = (600, 0)
    lp = nt.nodes.new('ShaderNodeLightPath'); lp.location = (300, 300)
    bg_black = nt.nodes.new('ShaderNodeBackground'); bg_black.location = (300, -200)
    bg_black.inputs['Color'].default_value = (0, 0, 0, 1)
    bg = nt.nodes.new('ShaderNodeBackground'); bg.name = "Reflets"; bg.location = (300, 50)
    bg.inputs['Strength'].default_value = 1.0
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-500, 0)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-300, 0)
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.location = (-100, 0)
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.location = (-200, 200)
    mr.inputs['From Min'].default_value, mr.inputs['From Max'].default_value = -1, 1
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (0.0, 0.0, 0.0, 1)
    el[1].position, el[1].color = 1.0, (0.08, 0.08, 0.09, 1)
    for pos, col in ((0.42, (0.02, 0.015, 0.01, 1)), (0.5, (2.6, 2.3, 1.9, 1)),
                     (0.56, (0.12, 0.1, 0.08, 1)), (0.8, (1.2, 1.15, 1.1, 1)), (0.9, (0.03, 0.03, 0.03, 1))):
        e = el.new(pos); e.color = col
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(bg_black.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    scene.world = w


def setup_lights(scene):
    specs = (("Cryptext clé", (-6, -9, 7), 3.0, 1100, (1.0, 0.92, 0.8)),
             ("Cryptext contre", (5, 6, 5), 4.0, 1200, (1.0, 0.85, 0.65)),
             ("Cryptext bas", (3, -6, -6), 3.0, 150, (0.85, 0.9, 1.0)))
    for name, loc, size, power, col in specs:
        ob = bpy.data.objects.get(name)
        if not ob:
            li = bpy.data.lights.new(name, 'AREA')
            ob = bpy.data.objects.new(name, li)
            scene.collection.objects.link(ob)
        ob.data.size, ob.data.energy, ob.data.color = size, power, col
        ob.location = loc
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = (-Vector(loc)).to_track_quat('-Z', 'Y')


def setup_camera(scene, dof=True):
    ob = bpy.data.objects.get("Cryptext caméra")
    if not ob:
        cam = bpy.data.cameras.new("Cryptext caméra")
        ob = bpy.data.objects.new("Cryptext caméra", cam)
        scene.collection.objects.link(ob)
    cam = ob.data
    cam.lens, cam.sensor_width, cam.sensor_fit = 50, 36, 'HORIZONTAL'
    cam.clip_start, cam.clip_end = 0.1, 200
    ob.location, ob.rotation_euler = (0, -CAM_DIST, 0), (math.radians(90), 0, 0)
    cam.dof.use_dof = dof
    cam.dof.focus_distance = CAM_DIST
    cam.dof.aperture_fstop = 4.0
    scene.camera = ob
    return ob


def setup_render(scene, fps=25):
    r = scene.render
    r.resolution_x = r.resolution_y = 1024
    r.resolution_percentage = 100
    r.fps = fps
    r.film_transparent = False
    try:
        r.engine = 'BLENDER_EEVEE'
    except TypeError:
        r.engine = 'BLENDER_EEVEE_NEXT'
    ee = scene.eevee
    for attr, val in (("use_raytracing", True), ("taa_render_samples", 64)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    scene.view_settings.view_transform = 'AgX'
    try:
        scene.view_settings.look = 'AgX - Punchy'
    except TypeError:
        pass


def fit_frame_range(scene, mod=None):
    mod = mod or get_modifier()
    if not mod:
        return
    end = get_input(mod, "Début pivot") + get_input(mod, "Durée pivot") + HOLD_AFTER
    scene.frame_start = 1
    scene.frame_end = int(math.ceil(end * scene.render.fps / scene.render.fps_base))


def input_ref(md, name):
    """(objet, nom de propriété) pour lire / afficher / animer une entrée du modificateur (Blender 4.x et 5.x)."""
    sid = md.node_group.interface.items_tree[name].identifier
    props = getattr(md, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        return getattr(props.inputs, sid), "value"
    return md, f'["{sid}"]'


def get_input(md, name):
    owner, prop = input_ref(md, name)
    return owner.value if prop == "value" else md[prop[2:-2]]


def set_input(md, name, value):
    owner, prop = input_ref(md, name)
    if prop == "value":
        owner.value = value
    else:
        md[prop[2:-2]] = value


def sync_circle(st):
    """Entrées cachées du réseau + cercle guide (non rendu) dans la vue caméra."""
    cam = bpy.data.objects.get("Cryptext caméra")
    md = get_modifier()
    if md and cam:
        set_input(md, "Zone ronde", bool(st.circle))
        set_input(md, "Demi-champ", (cam.data.sensor_width / 2) / cam.data.lens)
        set_input(md, "Rayon utile", st.circle_radius)
    guide = bpy.data.objects.get("Cryptext cercle (guide)")
    if cam and not guide:
        me = bpy.data.meshes.new("Cryptext cercle (guide)")
        k = 128
        me.from_pydata([(math.cos(2 * math.pi * i / k), math.sin(2 * math.pi * i / k), 0) for i in range(k)],
                       [(i, (i + 1) % k) for i in range(k)], [])
        guide = bpy.data.objects.new("Cryptext cercle (guide)", me)
        bpy.context.scene.collection.objects.link(guide)
        guide.parent = cam
        guide.hide_render = True
        guide.hide_select = True
        guide.display_type = 'WIRE'
    if guide and cam:
        r = (cam.data.sensor_width / 2) / cam.data.lens * 0.5
        guide.location = (0, 0, -0.5)
        guide.scale = (r, r, r)
        guide.hide_viewport = not st.circle


def get_object():
    return bpy.data.objects.get(OBJ)


def get_modifier():
    ob = get_object()
    if ob:
        for md in ob.modifiers:
            if md.type == 'NODES' and md.node_group and md.node_group.name.startswith(TREE):
                return md
    return None


def rebuild_points(st):
    build_points(st)
    sync_circle(st)


def rebuild_glyphs(st):
    font = load_font(st.font_path)
    coll, _ = build_glyphs(font, glyph_chars(st.number), st.extrude, st.bevel)
    build_points(st, font=font)
    return coll


def create_scene(st):
    scene = bpy.context.scene
    setup_render(scene)
    setup_camera(scene, st.use_dof)
    setup_world(scene)
    setup_lights(scene)
    apply_material_preset(st.material, st.roughness)
    font = load_font(st.font_path)
    coll, _ = build_glyphs(font, glyph_chars(st.number), st.extrude, st.bevel)

    ob = get_object()
    if not ob:
        ob = bpy.data.objects.new(OBJ, bpy.data.meshes.new("Cryptext points"))
        scene.collection.objects.link(ob)
    build_points(st, font=font)

    old = {}
    md = get_modifier()
    if md:  # garde les réglages déjà faits
        for it in md.node_group.interface.items_tree:
            if it.item_type == 'SOCKET' and it.in_out == 'INPUT' and it.socket_type != 'NodeSocketGeometry':
                try:
                    old[it.name] = get_input(md, it.name)
                except (KeyError, AttributeError, TypeError):
                    pass
        ob.modifiers.remove(md)
    tree = build_tree(coll)
    md = ob.modifiers.new("Cryptext", 'NODES')
    md.node_group = tree
    for it in tree.interface.items_tree:
        if it.item_type == 'SOCKET' and it.name in old:
            set_input(md, it.name, old[it.name])
    sync_circle(st)
    fit_frame_range(scene, md)
    scene.frame_set(scene.frame_current)
    return ob
