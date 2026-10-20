"""Escenas "en uso" para render.py (corre dentro de Blender): el producto real en su situación de uso.

Cada escena recibe el producto ya normalizado (centrado, apoyado en z=0, escala obj["escala"] = unidades por mm)
y arma los objetos de alrededor en milímetros reales. Devuelve (objetos a encuadrar, objetos visibles).

Las escenas dependen de cómo viene orientado cada modelo: se definen a mano por producto
(info.yaml > escena: {nombre: ..., parámetros}) y se prueban antes de usarlas.
"""
import math

import bpy
from mathutils import Matrix, Vector


def hex_a_lineal(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb] + [1.0]


# ---------- materiales ----------

def tela(color):
    m = bpy.data.materials.new("Tela")
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    p = n["Principled BSDF"]
    p.inputs["Base Color"].default_value = hex_a_lineal(color)
    p.inputs["Roughness"].default_value = 0.92
    for nombre, valor in (("Sheen Weight", 0.6), ("Sheen", 0.6)):
        if nombre in p.inputs:
            p.inputs[nombre].default_value = valor
    # trama de la tela: ruido muy fino como relieve
    coord = n.new("ShaderNodeTexCoord")
    ruido = n.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 900
    relieve = n.new("ShaderNodeBump")
    relieve.inputs["Strength"].default_value = 0.25
    l.new(coord.outputs["Object"], ruido.inputs["Vector"])
    l.new(ruido.outputs["Fac"], relieve.inputs["Height"])
    l.new(relieve.outputs["Normal"], p.inputs["Normal"])
    return m


def liso(color, rugosidad=0.5):
    m = bpy.data.materials.new("Liso")
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hex_a_lineal(color)
    p.inputs["Roughness"].default_value = rugosidad
    return m


# ---------- utilidades ----------

def malla(nombre, verts, caras, material, suave=True):
    me = bpy.data.meshes.new(nombre)
    me.from_pydata([tuple(v) for v in verts], [], caras)
    me.update()
    o = bpy.data.objects.new(nombre, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(material)
    if suave:
        for pol in me.polygons:
            pol.use_smooth = True
    return o


def solidificar(o, espesor):
    mod = o.modifiers.new("Espesor", "SOLIDIFY")
    mod.thickness = espesor
    mod.offset = 0
    return o


def revolucion(nombre, perfil, material, eje_desde, eje_hacia, lados=48):
    """Sólido de revolución: perfil = [(distancia sobre el eje, radio), ...] en las unidades de la escena."""
    eje = (Vector(eje_hacia) - Vector(eje_desde)).normalized()
    ref = Vector((0, 0, 1)) if abs(eje.z) < 0.9 else Vector((1, 0, 0))
    u = eje.cross(ref).normalized()
    v = eje.cross(u)
    verts, caras = [], []
    for d, r in perfil:
        for k in range(lados):
            a = 2 * math.pi * k / lados
            verts.append(Vector(eje_desde) + eje * d + (u * math.cos(a) + v * math.sin(a)) * r)
    for i in range(len(perfil) - 1):
        for k in range(lados):
            a, b = i * lados + k, i * lados + (k + 1) % lados
            caras.append((a, b, b + lados, a + lados))
    return malla(nombre, verts, caras, material)


def tee(desde, hacia, mm, color="#E2C9A0"):
    """Tee de golf de 54 mm: punta en `desde`, copa hacia `hacia`."""
    largo = 54
    perfil = [(0, 0.01), (6, 2.2), (44, 2.3), (49, 4.2), (52, 5.4), (54, 5.6), (54, 4.4), (53, 0.01)]
    eje = (Vector(hacia) - Vector(desde)).normalized()
    return revolucion("Tee", [(d * mm, r * mm) for d, r in perfil], liso(color, 0.55),
                      desde, Vector(desde) + eje * largo * mm)


# ---------- escenas ----------

def gorra(obj, color_gorra="#1F2A44", color_tee="#E2C9A0", ranura_z=5.6, ranura_x=-3.2, agujero=(-8.2, 5.6),
          lado_tee=-20):
    """Clip de tee calzado en la visera de una gorra, con un tee puesto.

    ranura_z: altura (mm) del plano medio de la ranura del clip; ranura_x: fondo de la ranura (mm, eje x del
    modelo centrado); la visera entra por +x. agujero: (x, z) del agujero del tee, que corre a lo largo de y.
    """
    mm = obj["escala"]
    R, L, caida = 92, 72, 26        # radio de la copa, largo de la visera al frente, caída de los costados
    zb = ranura_z * mm
    centro = Vector(((ranura_x + 0.3 + R + L) * mm, 0, 0))

    # visera: anillo entre la copa (r = R) y el borde (r = R + L·cos^0.8 φ), del frente a los costados
    seg, anillos = 72, 6
    verts, caras = [], []
    for i in range(seg + 1):
        fi = -math.pi / 2 + math.pi * i / seg
        afuera = R + L * max(math.cos(fi), 0) ** 0.8
        for j in range(anillos + 1):
            r = R + (afuera - R) * j / anillos
            x, y = centro.x / mm - r * math.cos(fi), r * math.sin(fi)
            z = ranura_z - caida * (y / (R + L)) ** 2 - 2.5 * (j / anillos) ** 2 * abs(math.sin(fi))
            verts.append(Vector((x, y, z)) * mm)
    for i in range(seg):
        for j in range(anillos):
            a = i * (anillos + 1) + j
            caras.append((a, a + 1, a + anillos + 2, a + anillos + 1))
    visera = solidificar(malla("Visera", verts, caras, tela(color_gorra)), 2.6 * mm)

    # costuras: 5 pespuntes paralelos al borde de la visera
    hilo = tela(color_gorra)
    hilo.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = [
        c * 0.55 for c in hex_a_lineal(color_gorra)[:3]] + [1]
    costuras = []
    for k in range(5):
        puntos = []
        for i in range(seg + 1):
            fi = -math.pi / 2 + math.pi * i / seg
            largo = L * max(math.cos(fi), 0) ** 0.8
            if largo < 12 + 5.5 * k:
                continue
            r = R + largo - (5 + 5.5 * k)
            y = r * math.sin(fi)
            fr = (r - R) / max(largo, 1e-6)
            z = ranura_z - caida * (y / (R + L)) ** 2 - 2.5 * fr ** 2 * abs(math.sin(fi)) + 1.3
            puntos.append(Vector((centro.x / mm - r * math.cos(fi), y, z)) * mm)
        cu = bpy.data.curves.new(f"Costura{k}", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.28 * mm
        sp = cu.splines.new("POLY")
        sp.points.add(len(puntos) - 1)
        for pt, v in zip(sp.points, puntos):
            pt.co = (*v, 1)
        o = bpy.data.objects.new(f"Costura{k}", cu)
        bpy.context.collection.objects.link(o)
        o.data.materials.append(hilo)
        costuras.append(o)

    # copa: media esfera achatada con botón arriba
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=R * mm,
                                         location=(centro.x, 0, zb - 4 * mm))
    copa = bpy.context.active_object
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.bisect(plane_co=(0, 0, zb - 4 * mm), plane_no=(0, 0, 1), clear_inner=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    copa.scale = (1.08, 1, 1.05)
    bpy.ops.object.shade_smooth()
    copa.data.materials.append(tela(color_gorra))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=6 * mm, location=(centro.x, 0, zb - 4 * mm + R * 1.05 * mm))
    boton = bpy.context.active_object
    boton.scale = (1, 1, 0.45)
    bpy.ops.object.shade_smooth()
    boton.data.materials.append(tela(color_gorra))

    ax, az = agujero
    t = tee(Vector((ax * mm, lado_tee * mm, az * mm)), Vector((ax * mm, -lado_tee * mm, az * mm)), mm, color_tee)
    return [obj, t], [obj, t, visera, copa, boton] + costuras


ESCENAS = {"gorra": gorra}


def construir(nombre, obj, **params):
    return ESCENAS[nombre](obj, **params)
