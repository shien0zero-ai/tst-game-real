"""Build the original exterior-only pistol prop with smooth bevelled meshes.

Run through build_m1911.py. Coordinates are authored in Godot metres and
converted to Blender's Z-up coordinates for glTF export.
"""
from pathlib import Path
from math import pi

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "models"
TEX = ROOT / "assets" / "textures"
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1.0
PARTS = {name: [] for name in ("slide", "frame", "grip", "magazine")}


def point(g):
    return Vector((g[0], -g[2], g[1]))


def material(name, color, metal, roughness, texture=None, normal_strength=0.35):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = roughness
    if texture:
        for suffix, socket, non_color in (("albedo", "Base Color", False),
                                           ("roughness", "Roughness", True),
                                           ("normal", None, True)):
            path = TEX / f"weapon_{texture}_{suffix}.png"
            image = bpy.data.images.load(str(path), check_existing=True)
            if non_color:
                image.colorspace_settings.name = "Non-Color"
            node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = image
            if suffix == "normal":
                normal = mat.node_tree.nodes.new("ShaderNodeNormalMap")
                normal.inputs["Strength"].default_value = normal_strength
                mat.node_tree.links.new(node.outputs["Color"], normal.inputs["Color"])
                mat.node_tree.links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
            else:
                mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs[socket])
    return mat


M = {
    "steel": material("Parkerized satin steel", (1, 1, 1), 0.92, 0.35, "steel", 0.08),
    "frame": material("Warm graphite frame", (0.19, 0.21, 0.22), 0.86, 0.43),
    "barrel": material("Machined barrel steel", (0.48, 0.51, 0.53), 0.98, 0.24),
    "black": material("Dark sight and recesses", (0.012, 0.015, 0.018), 0.35, 0.66),
    "walnut": material("Oiled double diamond walnut", (1, 1, 1), 0.0, 0.56, "walnut", 0.68),
    "white": material("Ivory sight inlays", (0.86, 0.88, 0.79), 0.0, 0.35),
}


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def finish(obj, name, group, mat, bevel=0.0006, segments=3, smooth=True, wood_uv=False):
    obj.name = name
    obj.data.materials.clear()
    obj.data.materials.append(M[mat])
    select_only(obj)
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name="UVMap")
    if wood_uv:
        uv = obj.data.uv_layers.active.data
        for polygon in obj.data.polygons:
            for loop_index in polygon.loop_indices:
                vertex = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
                # Position-only planar mapping; long grain follows the grip.
                g_y, g_z = vertex.z, -vertex.y
                uv[loop_index].uv = ((g_z + 0.018) / 0.036, (g_y + 0.096) / 0.096)
    else:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=1.1519173, island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")
    if bevel:
        mod = obj.modifiers.new("Soft machined edge", "BEVEL")
        mod.width = bevel
        mod.segments = segments
        mod.limit_method = "ANGLE"
        mod.harden_normals = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    if smooth:
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
        normal = obj.modifiers.new("Area weighted corner normals", "WEIGHTED_NORMAL")
        normal.keep_sharp = True
        normal.weight = 50
        bpy.ops.object.modifier_apply(modifier=normal.name)
    triangulate = obj.modifiers.new("Stable tangent triangulation", "TRIANGULATE")
    if hasattr(triangulate, "keep_custom_normals"):
        triangulate.keep_custom_normals = True
    bpy.ops.object.modifier_apply(modifier=triangulate.name)
    if group:
        PARTS[group].append(obj)
    return obj


def cube_raw(name, size, pos, rot_x=0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=point(pos))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (size[0], size[2], size[1])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler.x = rot_x
    return obj


def box(name, group, mat, size, pos, bevel=0.0006, rot_x=0):
    return finish(cube_raw(name, size, pos, rot_x), name, group, mat, bevel)


def cylinder_raw(name, radius, depth, pos, axis=(0, 0, 1), vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=point(pos))
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(point(axis).normalized())
    return obj


def cylinder(name, group, mat, radius, depth, pos, axis=(0, 0, 1), bevel=0.00025):
    return finish(cylinder_raw(name, radius, depth, pos, axis), name, group, mat, bevel)


def mesh_object(name, vertices, faces):
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata([point(v) for v in vertices], [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def extrude_z(name, profile_xy, rear, front):
    count = len(profile_xy)
    vertices = [(x, y, z) for z in (rear, front) for x, y in profile_xy]
    faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, 2 * count))]
    faces += [(i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count)]
    return mesh_object(name, vertices, faces)


def extrude_x(name, profile_yz, left, right):
    count = len(profile_yz)
    vertices = [(x, y, z) for x in (left, right) for y, z in profile_yz]
    faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, 2 * count))]
    faces += [(i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count)]
    return mesh_object(name, vertices, faces)


def difference(obj, cutter):
    select_only(obj)
    mod = obj.modifiers.new("Exterior machined opening", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def hollow_ring(name, group, mat, outer, inner, depth, pos, axis=(0, 0, 1)):
    obj = cylinder_raw(name, outer, depth, pos, axis)
    difference(obj, cylinder_raw("Bore tool", inner, depth * 2, pos, axis))
    return finish(obj, name, group, mat, 0.00016)


# A single machined slide, rather than intersecting box/cylinder primitives.
slide_profile = [(-0.0165, -0.014), (-0.0165, 0.008), (-0.0156, 0.013),
                 (-0.0125, 0.019), (-0.008, 0.023), (-0.004, 0.0245),
                 (0.004, 0.0245), (0.008, 0.023), (0.0125, 0.019),
                 (0.0156, 0.013), (0.0165, 0.008), (0.0165, -0.014)]
slide = extrude_z("SlideBody", slide_profile, 0.005, -0.182)
difference(slide, cylinder_raw("Barrel opening", 0.0097, 0.06, (0, 0.004, -0.181)))
difference(slide, cube_raw("Ejection opening", (0.027, 0.029, 0.035), (0.012, 0.014, -0.071)))
for side in (-1, 1):
    for i in range(9):
        difference(slide, cube_raw("Serration tool", (0.003, 0.025, 0.0013),
                                   (side * 0.0167, -0.0003, -0.004 - i * 0.0036), 0.12))
finish(slide, "SlideBody", "slide", "steel", 0.00065, 4)
# Thin rails and port cavity give useful depth at the top-side view.
box("SlideRailSeam", "slide", "black", (0.0334, 0.0010, 0.179), (0, -0.0142, -0.088), 0.0002)
box("RearSightBase", "slide", "black", (0.025, 0.0035, 0.009), (0, 0.0275, -0.004), 0.00045)
for label, x in (("Left", -0.0085), ("Right", 0.0085)):
    box("RearSight" + label, "slide", "black", (0.0065, 0.008, 0.008), (x, 0.033, -0.004), 0.00065)
    cylinder("RearDot" + label, "slide", "white", 0.0012, 0.0006, (x, 0.033, 0.0003), bevel=0.0001)
box("FrontSight", "slide", "black", (0.004, 0.006, 0.013), (0, 0.028, -0.169), 0.00045)
cylinder("FrontSightDot", "slide", "white", 0.0011, 0.0006, (0, 0.028, -0.1621), bevel=0.0001)

# Steel frame and a separate, stationary barrel visible inside the open port.
frame_profile = [(-0.016, -0.015), (-0.016, -0.029), (-0.011, -0.036),
                 (0.011, -0.036), (0.016, -0.029), (0.016, -0.015)]
finish(extrude_z("FrameRail", frame_profile, 0.006, -0.163), "FrameRail", "frame", "frame", 0.001, 4)
box("DustCover", "frame", "frame", (0.026, 0.018, 0.074), (0, -0.032, -0.121), 0.002)
cylinder("BarrelInsidePort", "frame", "barrel", 0.0078, 0.14, (0, 0.004, -0.119), bevel=0.00035)
hollow_ring("BarrelBushing", "frame", "steel", 0.012, 0.0089, 0.004, (0, 0.004, -0.183))
hollow_ring("MuzzleCrown", "frame", "barrel", 0.0091, 0.00565, 0.010, (0, 0.004, -0.191))
cylinder("BoreDarkness", "frame", "black", 0.0056, 0.001, (0, 0.004, -0.182), bevel=0)
cylinder("RecoilPlug", "frame", "steel", 0.0055, 0.005, (0, -0.014, -0.182), bevel=0.00045)

outer_guard = [(-0.031, -0.085), (-0.039, -0.093), (-0.059, -0.095),
               (-0.071, -0.089), (-0.076, -0.077), (-0.076, -0.052),
               (-0.069, -0.037), (-0.034, -0.036)]
inner_guard = [(-0.041, -0.082), (-0.045, -0.087), (-0.059, -0.088),
               (-0.067, -0.083), (-0.069, -0.074), (-0.069, -0.051),
               (-0.064, -0.044), (-0.041, -0.044)]
guard = extrude_x("RoundedTriggerGuard", outer_guard, -0.0055, 0.0055)
difference(guard, extrude_x("Guard opening", inner_guard, -0.02, 0.02))
finish(guard, "RoundedTriggerGuard", "frame", "frame", 0.00125, 5)
trigger_profile = [(-0.031, -0.052), (-0.033, -0.057), (-0.042, -0.061),
                   (-0.053, -0.061), (-0.055, -0.057), (-0.043, -0.056), (-0.035, -0.051)]
trigger = extrude_x("CurvedTrigger", trigger_profile, -0.0058, 0.0058)
for y in (-0.036, -0.043, -0.050):
    difference(trigger, cylinder_raw("Trigger recess", 0.0014, 0.02, (0, y, -0.057), (1, 0, 0)))
finish(trigger, "CurvedTrigger", "frame", "barrel", 0.0005, 3)

box("Beavertail", "frame", "frame", (0.023, 0.007, 0.027), (0, -0.024, 0.017), 0.0015, -0.25)
box("HammerSpur", "frame", "barrel", (0.010, 0.0075, 0.019), (0, 0.012, 0.015), 0.0013, -0.35)
for i in range(5):
    box("HammerRidge%02d" % i, "frame", "black", (0.009, 0.0006, 0.0007),
        (0, 0.0163, 0.009 + i * 0.0025), 0.00012)
box("ThumbSafety", "frame", "steel", (0.005, 0.004, 0.018), (-0.0184, -0.023, -0.009), 0.0010)
box("SlideStop", "frame", "steel", (0.0035, 0.004, 0.024), (-0.0178, -0.023, -0.057), 0.0007)
cylinder("SlideStopPin", "frame", "barrel", 0.0031, 0.003, (-0.018, -0.024, -0.041), (1, 0, 0))
cylinder("MagazineCatch", "frame", "steel", 0.0035, 0.003, (-0.0188, -0.036, -0.026), (1, 0, 0))

# Grip geometry is local to the original, inclined Grip node in the wrapper.
grip_profile = [(-0.001, -0.015), (-0.003, 0.016), (-0.034, 0.020),
                (-0.078, 0.020), (-0.094, 0.014), (-0.096, -0.012),
                (-0.082, -0.019), (-0.027, -0.019)]
finish(extrude_x("GripFrame", grip_profile, -0.0168, 0.0168), "GripFrame", "grip", "frame", 0.0025, 5)
panel_profile = [(-0.008, -0.012), (-0.010, 0.013), (-0.074, 0.015),
                 (-0.088, 0.010), (-0.089, -0.010), (-0.079, -0.014), (-0.020, -0.014)]
for label, side in (("Left", -1), ("Right", 1)):
    a, b = sorted((side * 0.0176, side * 0.0223))
    obj = extrude_x(label + "WalnutGrip", panel_profile, a, b)
    finish(obj, label + "WalnutGrip", "grip", "walnut", 0.0017, 5, wood_uv=True)
    for index, y in enumerate((-0.016, -0.079)):
        screw = cylinder_raw(label + "GripScrew%d" % index, 0.0026, 0.001,
                             (side * 0.0229, y, 0.0007), (1, 0, 0))
        difference(screw, cube_raw("Screw slot", (0.004, 0.00065, 0.0033),
                                   (side * 0.0235, y, 0.0007)))
        finish(screw, label + "GripScrew%d" % index, "grip", "barrel", 0.00015, 3)
box("Backstrap", "grip", "steel", (0.026, 0.085, 0.004), (0, -0.045, 0.0198), 0.0015)
for i in range(12):
    box("BackstrapGroove%02d" % i, "grip", "black", (0.023, 0.0005, 0.0005),
        (0, -0.016 - i * 0.0057, 0.0220), 0.0001)

# The lower magazine wrapper remains independently movable during reload.
box("MagazineBaseplate", "magazine", "steel", (0.036, 0.006, 0.040), (0, 0, 0), 0.0014)
box("MagazineLowerWall", "magazine", "frame", (0.025, 0.012, 0.029), (0, 0.007, 0), 0.0005)

for group, objects in PARTS.items():
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    path = OUT / f"m1911_{group}.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_texcoords=True,
                              export_normals=True, export_tangents=True,
                              export_materials="EXPORT", export_image_format="AUTO")
    print(f"Exported {path.name}: {len(objects)} exterior parts")

print("M1911 exterior model export completed.")
