"""Render de estudio de un modelo 3D (STL/3MF/OBJ) con Blender, gratis y sin IA.

Uso (lo llama agente/fotos.py, no hace falta usarlo a mano):
    blender -b -P agente/render.py -- modelo.stl salida.png --color "#E5262B" \
        [--angulo 35] [--giro 30] [--fondo "#F4F1EA"] [--tam 1080] [--muestras 96]
"""
import argparse
import math
import sys

import bpy
from mathutils import Matrix, Vector


def hex_a_lineal(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb] + [1.0]


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument("modelo")
    ap.add_argument("salida")
    ap.add_argument("--color", default="#016040")
    ap.add_argument("--fondo", default="#F4F1EA")
    ap.add_argument("--angulo", type=float, default=32, help="elevación de la cámara en grados")
    ap.add_argument("--giro", type=float, default=35, help="rotación alrededor del modelo en grados")
    ap.add_argument("--tam", type=int, default=1080)
    ap.add_argument("--muestras", type=int, default=96)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return ap.parse_args(argv)


def importar(ruta):
    ext = ruta.lower().rsplit(".", 1)[-1]
    antes = set(bpy.data.objects)
    if ext == "stl":
        try:
            bpy.ops.wm.stl_import(filepath=ruta)
        except AttributeError:
            bpy.ops.import_mesh.stl(filepath=ruta)
    elif ext == "obj":
        bpy.ops.wm.obj_import(filepath=ruta)
    elif ext == "3mf":
        bpy.ops.import_mesh.threemf(filepath=ruta)
    else:
        raise SystemExit(f"Formato no soportado: {ext}")
    objs = [o for o in bpy.data.objects if o not in antes and o.type == "MESH"]
    if not objs:
        raise SystemExit("El archivo no tiene mallas")
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def normalizar(obj):
    """Centra el modelo, lo apoya en el piso y lo escala a ~1 unidad (modificando la malla)."""
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    pts = [v.co for v in obj.data.vertices]
    mins = Vector([min(p[i] for p in pts) for i in range(3)])
    maxs = Vector([max(p[i] for p in pts) for i in range(3)])
    escala = 1.0 / max(maxs - mins)
    centro = Vector(((mins.x + maxs.x) / 2, (mins.y + maxs.y) / 2, mins.z))
    obj.data.transform(Matrix.Scale(escala, 4) @ Matrix.Translation(-centro))
    obj.data.update()
    bpy.context.view_layer.update()
    obj.data.shade_smooth()
    if hasattr(obj.data, "use_auto_smooth"):
        obj.data.use_auto_smooth = True
        obj.data.auto_smooth_angle = math.radians(35)


def material_pla(obj, color):
    m = bpy.data.materials.new("PLA")
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hex_a_lineal(color)
    p.inputs["Roughness"].default_value = 0.42
    if "Specular IOR Level" in p.inputs:
        p.inputs["Specular IOR Level"].default_value = 0.45
    obj.data.materials.clear()
    obj.data.materials.append(m)


def escenario(fondo):
    # Piso curvo tipo estudio (sin horizonte visible)
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    piso = bpy.context.active_object
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=40)
    bpy.ops.object.mode_set(mode="OBJECT")
    for v in piso.data.vertices:
        if v.co.y > 1.5:
            v.co.z = (v.co.y - 1.5) ** 2 * 0.35
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new("Fondo")
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hex_a_lineal(fondo)
    p.inputs["Roughness"].default_value = 0.9
    piso.data.materials.append(m)

    mundo = bpy.context.scene.world or bpy.data.worlds.new("Mundo")
    bpy.context.scene.world = mundo
    mundo.use_nodes = True
    bg = mundo.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = hex_a_lineal(fondo)
    bg.inputs["Strength"].default_value = 0.45


def luz(nombre, pos, energia, tam):
    d = bpy.data.lights.new(nombre, type="AREA")
    d.energy = energia
    d.size = tam
    o = bpy.data.objects.new(nombre, d)
    bpy.context.collection.objects.link(o)
    o.location = pos
    direccion = Vector((0, 0, 0.35)) - Vector(pos)
    o.rotation_euler = direccion.to_track_quat("-Z", "Y").to_euler()


def camara(obj, angulo, giro):
    centro = Vector((0, 0, obj.dimensions.z / 2))
    radio = obj.dimensions.length * 0.5 * 1.02
    cam_d = bpy.data.cameras.new("Cam")
    cam_d.lens = 85
    cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    # distancia para que el modelo entre en el cuadro con un 85 mm
    fov = 2 * math.atan(cam_d.sensor_width / (2 * cam_d.lens))
    dist = radio / math.sin(fov / 2)
    a, g = math.radians(angulo), math.radians(giro)
    cam.location = centro + Vector((math.sin(g) * math.cos(a), -math.cos(g) * math.cos(a), math.sin(a))) * dist
    cam.rotation_euler = (centro - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam


def main():
    a = args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = importar(a.modelo)
    normalizar(obj)
    material_pla(obj, a.color)
    escenario(a.fondo)
    luz("Principal", (-2.5, -2.5, 3.5), 520, 3)
    luz("Relleno", (3, -2, 1.5), 140, 4)
    luz("Contra", (0.5, 3, 2.5), 260, 2)
    camara(obj, a.angulo, a.giro)

    esc = bpy.context.scene
    esc.render.engine = "CYCLES"
    esc.cycles.device = "CPU"
    # El Blender de Ubuntu viene sin el quitarruido: en ese caso compensamos con más muestras
    con_oidn = getattr(bpy.app.build_options, "openimagedenoise", False)
    esc.cycles.use_denoising = con_oidn
    esc.cycles.samples = a.muestras if con_oidn else a.muestras * 4
    esc.render.resolution_x = esc.render.resolution_y = a.tam
    # "Standard" respeta el color real del filamento (AgX/Filmic lo desaturan)
    esc.view_settings.view_transform = "Standard"
    esc.view_settings.look = "None"
    esc.view_settings.exposure = -1.0
    esc.render.image_settings.file_format = "PNG"
    esc.render.filepath = a.salida
    bpy.ops.render.render(write_still=True)


main()
