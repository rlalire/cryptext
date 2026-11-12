# Cryptext : réglages, opérateurs et panneau (barre latérale N › Cryptext).
import bpy
from bpy.props import (StringProperty, IntProperty, FloatProperty, EnumProperty, BoolProperty, PointerProperty,
                       CollectionProperty)
from . import core


def _points(self, ctx):
    if core.get_object():
        core.rebuild_points(self)


def sync_chars(st):
    """Une ligne de réglage par caractère du nombre (garde les décalages des caractères inchangés)."""
    want = [c for c in st.number if not c.isspace()]
    old = [(it.char, it.x, it.z) for it in st.chars]
    if [o[0] for o in old] == want:
        return
    st.chars.clear()
    for k, c in enumerate(want):
        it = st.chars.add()
        it.char = c
        if k < len(old) and old[k][0] == c:
            it["x"], it["z"] = old[k][1], old[k][2]


def _glyphs(self, ctx):
    sync_chars(self)
    if core.get_object():
        core.rebuild_glyphs(self)


def _char(self, ctx):
    st = ctx.scene.cryptext
    if core.get_object():
        core.rebuild_points(st)


class CryptextChar(bpy.types.PropertyGroup):
    char: StringProperty(name="Caractère")
    x: FloatProperty(name="X", default=0.0, step=1, precision=3, update=_char,
                     description="Décalage horizontal (en hauteur de lettre) ; négatif = vers la gauche")
    z: FloatProperty(name="Y", default=0.0, step=1, precision=3, update=_char,
                     description="Décalage vertical (en hauteur de lettre)")


def _material(self, ctx):
    core.apply_material_preset(self.material, self.roughness)


def _material_preset(self, ctx):
    self["roughness"] = core.MATERIALS[self.material][2]
    core.apply_material_preset(self.material, self.roughness)


def _dof(self, ctx):
    cam = bpy.data.objects.get("Cryptext caméra")
    if cam:
        cam.data.dof.use_dof = self.use_dof


class CryptextSettings(bpy.types.PropertyGroup):
    font_path: StringProperty(name="Police", subtype='FILE_PATH', default="",
                              description="Fichier .ttf / .otf (vide = Cryptext25 fournie)", update=_glyphs)
    number: StringProperty(name="Nombre", default="10106",
                           description="Nombre qui reste à la fin puis pivote", update=_glyphs)
    count: IntProperty(name="Chiffres", default=500, min=0, max=20000, update=_points,
                       description="Nombre de chiffres dans le nuage")
    seed: IntProperty(name="Graine", default=7, min=0, update=_points)
    spread: FloatProperty(name="Débord", default=1.0, min=0.3, max=3.0, update=_points,
                          description="Largeur du nuage par rapport au cadre")
    depth_front: FloatProperty(name="Profondeur avant", default=5.0, min=0.0, max=11.0, unit='LENGTH',
                               update=_points, description="Jusqu'où les chiffres s'approchent de la caméra")
    depth_back: FloatProperty(name="Profondeur arrière", default=8.0, min=0.0, max=100.0, unit='LENGTH',
                              update=_points, description="Jusqu'où les chiffres s'enfoncent dans le noir")
    size_min: FloatProperty(name="Taille min", default=0.15, min=0.01, max=5.0, update=_points,
                            description="Taille des chiffres du nuage, relative au nombre final")
    size_max: FloatProperty(name="Taille max", default=0.4, min=0.01, max=5.0, update=_points)
    number_width: FloatProperty(name="Largeur du nombre", default=0.62, min=0.05, max=1.0, subtype='FACTOR',
                                update=_points, description="Part de la largeur de l'image occupée par le nombre")
    clearance: FloatProperty(name="Dégagement", default=0.25, min=0.0, max=5.0, unit='LENGTH', update=_points,
                             description="Espace laissé libre autour du nombre, à sa profondeur")
    extrude: FloatProperty(name="Épaisseur", default=0.07, min=0.0, max=1.0, update=_glyphs,
                           description="Épaisseur des chiffres (en hauteur de lettre)")
    bevel: FloatProperty(name="Biseau", default=0.012, min=0.0, max=0.2, update=_glyphs)
    material: EnumProperty(name="Matière", items=(('GOLD', "Or", ""), ('SILVER', "Argent", ""),
                                                  ('WHITE', "Blanc", "")), default='GOLD', update=_material_preset)
    roughness: FloatProperty(name="Rugosité", default=0.18, min=0.0, max=1.0, subtype='FACTOR', update=_material)
    use_dof: BoolProperty(name="Profondeur de champ", default=True, update=_dof)
    chars: CollectionProperty(type=CryptextChar)
    spacing: FloatProperty(name="Espacement", default=0.0, min=-1.0, max=2.0, step=1, precision=3, update=_points,
                           description="Espace ajouté entre les caractères du nombre (en hauteur de lettre)")
    circle: BoolProperty(name="Zone ronde", default=True, update=_points,
                         description="Hélice holographique : rien ne touche le bord du cercle inscrit dans l'image")
    circle_radius: FloatProperty(name="Rayon utile", default=0.97, min=0.3, max=1.0, subtype='FACTOR',
                                 update=_points, description="Rayon du cercle utile (1 = bord du cercle de 1024 px)")


class CRYPTEXT_OT_create(bpy.types.Operator):
    bl_idname = "cryptext.create"
    bl_label = "Créer / reconstruire la scène"
    bl_description = "Crée caméra 1024×1024, fond noir, lumières, glyphes 3D et le nuage animé"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        sync_chars(ctx.scene.cryptext)
        core.create_scene(ctx.scene.cryptext)
        return {'FINISHED'}


class CRYPTEXT_OT_fit(bpy.types.Operator):
    bl_idname = "cryptext.fit_range"
    bl_label = "Ajuster la durée"
    bl_description = "Fin de la scène = fin du pivot + 4 s"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        core.fit_frame_range(ctx.scene)
        return {'FINISHED'}


class CRYPTEXT_OT_jump(bpy.types.Operator):
    bl_idname = "cryptext.jump"
    bl_label = "Aller à"
    bl_options = {'REGISTER'}
    socket: StringProperty()

    def execute(self, ctx):
        md = core.get_modifier()
        sc = ctx.scene
        sc.frame_set(int(round(core.get_input(md, self.socket) * sc.render.fps / sc.render.fps_base)) + 1)
        return {'FINISHED'}


class CRYPTEXT_OT_reset_chars(bpy.types.Operator):
    bl_idname = "cryptext.reset_chars"
    bl_label = "Remettre à zéro"
    bl_description = "Annule les décalages et l'espacement du nombre"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = ctx.scene.cryptext
        for it in st.chars:
            it["x"] = it["z"] = 0.0
        st.spacing = 0.0
        return {'FINISHED'}


class CRYPTEXT_OT_jump_end(bpy.types.Operator):
    bl_idname = "cryptext.jump_end"
    bl_label = "Voir le mot"
    bl_description = "Place la tête de lecture après le pivot"
    bl_options = {'REGISTER'}

    def execute(self, ctx):
        md, sc = core.get_modifier(), ctx.scene
        t = core.get_input(md, "Début pivot") + core.get_input(md, "Durée pivot") + 0.5
        sc.frame_set(int(round(t * sc.render.fps / sc.render.fps_base)) + 1)
        return {'FINISHED'}


class CRYPTEXT_PT_main(bpy.types.Panel):
    bl_space_type, bl_region_type, bl_category = 'VIEW_3D', 'UI', "Cryptext"
    bl_label = "Cryptext"

    def draw(self, ctx):
        st, lay = ctx.scene.cryptext, self.layout
        lay.operator("cryptext.create", icon='FILE_REFRESH')
        col = lay.column(align=True)
        col.prop(st, "number")
        col.prop(st, "font_path")
        if not core.get_object():
            lay.label(text="Cliquez sur « Créer » pour commencer.", icon='INFO')


class _Sub:
    bl_space_type, bl_region_type, bl_category = 'VIEW_3D', 'UI', "Cryptext"
    bl_parent_id = "CRYPTEXT_PT_main"

    @classmethod
    def poll(cls, ctx):
        return core.get_object() is not None


class CRYPTEXT_PT_number(_Sub, bpy.types.Panel):
    bl_label = "Position des caractères"

    def draw(self, ctx):
        st, lay = ctx.scene.cryptext, self.layout
        row = lay.row(align=True)
        op = row.operator("cryptext.jump", text="Avant le pivot", icon='TIME'); op.socket = "Début pivot"
        row.operator("cryptext.jump_end", text="Voir le mot", icon='FILE_REFRESH')
        lay.prop(st, "spacing")
        col = lay.column(align=True)
        for it in st.chars:
            r = col.row(align=True)
            r.label(text=it.char)
            r.prop(it, "x")
            r.prop(it, "z")
        lay.operator("cryptext.reset_chars", icon='LOOP_BACK')


class CRYPTEXT_PT_circle(_Sub, bpy.types.Panel):
    bl_label = "Zone ronde (hélice)"

    def draw_header(self, ctx):
        self.layout.prop(ctx.scene.cryptext, "circle", text="")

    def draw(self, ctx):
        st, lay = ctx.scene.cryptext, self.layout
        lay.use_property_split = True
        lay.active = st.circle
        lay.prop(st, "circle_radius")
        md = core.get_modifier()
        if md:
            owner, prop = core.input_ref(md, "Fondu au bord")
            lay.prop(owner, prop, text="Fondu au bord")
        if st.get("_limited"):
            lay.label(text="Nombre réduit pour tenir dans le cercle", icon='INFO')


class CRYPTEXT_PT_cloud(_Sub, bpy.types.Panel):
    bl_label = "Nuage"

    def draw(self, ctx):
        st, lay = ctx.scene.cryptext, self.layout
        lay.use_property_split = True
        col = lay.column(align=True)
        col.prop(st, "count"); col.prop(st, "seed")
        col = lay.column(align=True)
        col.prop(st, "size_min"); col.prop(st, "size_max")
        col = lay.column(align=True)
        col.prop(st, "spread"); col.prop(st, "depth_front"); col.prop(st, "depth_back")
        col = lay.column(align=True)
        col.prop(st, "number_width"); col.prop(st, "clearance")


class CRYPTEXT_PT_look(_Sub, bpy.types.Panel):
    bl_label = "Matière et rendu"

    def draw(self, ctx):
        st, lay = ctx.scene.cryptext, self.layout
        lay.use_property_split = True
        lay.prop(st, "material", expand=True)
        lay.prop(st, "roughness")
        col = lay.column(align=True)
        col.prop(st, "extrude"); col.prop(st, "bevel")
        lay.prop(st, "use_dof")
        cam = bpy.data.objects.get("Cryptext caméra")
        if cam and st.use_dof:
            lay.prop(cam.data.dof, "aperture_fstop", text="Ouverture f/")
        w = ctx.scene.world
        if w and w.node_tree and "Reflets" in w.node_tree.nodes:
            lay.prop(w.node_tree.nodes["Reflets"].inputs['Strength'], "default_value", text="Reflets")
        lay.prop(ctx.scene.render, "use_motion_blur", text="Flou de mouvement")


def _draw_inputs(lay, md, panel_name, jump=None):
    tree = md.node_group
    for name, typ, *_ in dict(core.PANELS)[panel_name]:
        if name in core.HIDDEN:
            continue
        it = tree.interface.items_tree.get(name)
        if not it:
            continue
        row = lay.row(align=True)
        owner, prop = core.input_ref(md, name)
        row.prop(owner, prop, text=name)
        if name == "Mode pivot":
            lay.label(text=core.PIVOT_MODES[max(0, min(2, core.get_input(md, name)))], icon='ORIENTATION_GIMBAL')
            continue
        if name == jump:
            row.operator("cryptext.jump", text="", icon='TIME').socket = name


def _make_timing_panel(pname, jump):
    def draw(self, ctx):
        md = core.get_modifier()
        if md:
            self.layout.use_property_split = True
            _draw_inputs(self.layout, md, pname, jump)
    import unicodedata
    ascii_name = unicodedata.normalize('NFKD', pname).encode('ascii', 'ignore').decode()
    ident = "CRYPTEXT_PT_" + "".join(ch for ch in ascii_name.lower() if ch.isalpha())
    return type(ident, (_Sub, bpy.types.Panel), {"bl_label": pname, "bl_idname": ident, "draw": draw,
                                                  "bl_options": {'DEFAULT_CLOSED'} if pname != "Apparition" else set()})


TIMING = [_make_timing_panel(p, j) for p, j in (("Apparition", "Début apparition"), ("Flottement", "Immobile à"),
                                                 ("Agitation", "Début agitation"), ("Répulsion", "Début répulsion"), ("Nombre", None),
                                                 ("Pivot", "Début pivot"))]


class CRYPTEXT_PT_timeline(_Sub, bpy.types.Panel):
    bl_label = "Durée"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        sc, lay = ctx.scene, self.layout
        row = lay.row(align=True)
        row.prop(sc.render, "fps", text="Images/s")
        row.prop(sc, "frame_end", text="Fin")
        lay.operator("cryptext.fit_range", icon='TIME')


CLASSES = [CryptextChar, CryptextSettings, CRYPTEXT_OT_create, CRYPTEXT_OT_fit, CRYPTEXT_OT_jump,
           CRYPTEXT_OT_reset_chars, CRYPTEXT_OT_jump_end, CRYPTEXT_PT_main, CRYPTEXT_PT_number, CRYPTEXT_PT_circle,
           CRYPTEXT_PT_cloud, *TIMING, CRYPTEXT_PT_look, CRYPTEXT_PT_timeline]


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.cryptext = PointerProperty(type=CryptextSettings)


def unregister():
    del bpy.types.Scene.cryptext
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
