# Test sans interface : crée la scène et rend quelques images clés.
# python tools/render_test.py <dossier_sortie> [échantillons] [secondes...]
import sys, os, importlib.util, bpy
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "addon"))
import cryptext
cryptext.register()
out = os.path.abspath(sys.argv[1]); os.makedirs(out, exist_ok=True)
samples = int(sys.argv[2]) if len(sys.argv) > 2 else 16
times = [float(x) for x in sys.argv[3:]] or [2, 10, 20, 30, 32, 34, 36, 38, 41, 42.5, 44, 46]
sc = bpy.context.scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
core = cryptext.core
core.create_scene(sc.cryptext)
sc.eevee.taa_render_samples = samples
if os.environ.get("CRYPTEXT_CYCLES"):          # machine sans GPU : rendu Cycles sur CPU
    sc.render.engine = 'CYCLES'
    sc.cycles.device, sc.cycles.samples, sc.cycles.use_denoising = 'CPU', samples, True
    sc.render.resolution_percentage = int(os.environ.get("CRYPTEXT_PCT", "50"))
md = core.get_modifier()
print("objets:", len(bpy.data.objects), "frames", sc.frame_start, sc.frame_end)
for t in times:
    f = int(round(t * sc.render.fps)) + 1
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, f"t{t:05.1f}.png")
    bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "cryptext_test.blend"))
