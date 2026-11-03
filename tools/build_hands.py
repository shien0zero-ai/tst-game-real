#!/usr/bin/env python3
"""Build original gloved FPS hands with Blender (no downloaded geometry).

    blender --background --factory-startup --python tools/build_hands.py

Authoring positions are expressed in Godot's X-right/Y-up/Z-back convention.
The two exported GLBs share the pistol's local origin, making support-hand
reload movement possible without a skeleton dependency.
"""
from pathlib import Path
import math
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "assets" / "models"
SCRATCH = ROOT / "work" / "hands-authoring"
MODELS.mkdir(parents=True, exist_ok=True)
SCRATCH.mkdir(parents=True, exist_ok=True)
(ROOT / "work" / ".gdignore").touch()

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)


def position(point):
    """Godot coordinates to Blender coordinates before the glTF Y-up export."""
    return Vector((point[0], -point[2], point[1]))


def material(name, color, roughness):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    return result


fabric = material("Hands woven charcoal", (0.115, 0.13, 0.14), 0.92)
rubber = material("Hands rubber reinforcement", (0.043, 0.05, 0.055), 0.88)
thread = material("Hands stitched seams", (0.21, 0.225, 0.21), 0.96)
sleeve = material("Hands cotton sleeve", (0.13, 0.15, 0.135), 0.96)
cuff = material("Hands elastic cuff", (0.068, 0.077, 0.074), 0.96)

# A tiny original woven normal map is embedded into each glTF material.
image = bpy.data.images.new("Original glove weave", width=128, height=128, alpha=False)
pixels = []
for y in range(128):
    for x in range(128):
        a = math.sin(x * math.pi / 2.0) * 0.045
        b = math.sin(y * math.pi / 2.0) * 0.045
        grain = (((x * 73 + y * 151) % 101) / 100.0 - 0.5) * 0.016
        pixels.extend((0.5 + a + grain, 0.5 + b - grain, 0.989, 1.0))
image.colorspace_settings.name = "Non-Color"
image.pixels = pixels
image.filepath_raw = str(SCRATCH / "glove-weave.png")
image.file_format = "PNG"
image.save()
image.pack()
for mat in (fabric, sleeve, cuff):
    nodes = mat.node_tree.nodes
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.extension = "REPEAT"
    normal = nodes.new("ShaderNodeNormalMap")
    normal.inputs["Strength"].default_value = 0.15 if mat == fabric else 0.08
    mat.node_tree.links.new(texture.outputs["Color"], normal.inputs["Color"])
    mat.node_tree.links.new(normal.outputs["Normal"], nodes.get("Principled BSDF").inputs["Normal"])


def group(name):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    return obj


def finish(obj, parent, mat):
    obj.parent = parent
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def rounded_box(name, point, dimensions, parent, mat, radius=0.005, pitch=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=position(point))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (dimensions[0], dimensions[2], dimensions[1])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler.x = pitch
    bevel = obj.modifiers.new("Soft glove edges", "BEVEL")
    bevel.width = min(radius, min(dimensions) * 0.48)
    bevel.segments = 3
    bevel.affect = "EDGES"
    bevel.harden_normals = True
    weighted = obj.modifiers.new("Balanced surface normals", "WEIGHTED_NORMAL")
    weighted.keep_sharp = True
    return finish(obj, parent, mat)


def smooth_path(points, samples=4):
    data = [Vector(p) for p in points]
    result = []
    for i in range(len(data) - 1):
        p0, p1 = data[max(0, i - 1)], data[i]
        p2, p3 = data[i + 1], data[min(len(data) - 1, i + 2)]
        for step in range(samples):
            t = step / samples
            result.append(0.5 * ((2.0 * p1) + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t*t
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t*t*t))
    result.append(data[-1])
    return result


def tube(name, points, radii, parent, mat, flatten=0.84, sides=12):
    path = smooth_path(points)
    verts, faces = [], []
    for i, p in enumerate(path):
        t = i / (len(path) - 1)
        section = t * (len(radii) - 1)
        a = min(int(section), len(radii) - 2)
        radius = radii[a] * (1 - (section - a)) + radii[a + 1] * (section - a)
        direction = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
        direction.normalize()
        ref = Vector((0, 1, 0)) if abs(direction.y) < 0.9 else Vector((1, 0, 0))
        across = direction.cross(ref).normalized()
        vertical = direction.cross(across).normalized()
        for j in range(sides):
            angle = j * math.tau / sides
            q = p + across * math.cos(angle) * radius + vertical * math.sin(angle) * radius * flatten
            verts.append(position(q))
        if i:
            for j in range(sides):
                a0, a1 = (i - 1) * sides + j, (i - 1) * sides + (j + 1) % sides
                b0, b1 = i * sides + j, i * sides + (j + 1) % sides
                faces.append((a0, a1, b1, b0))
    for j in range(1, sides - 1):
        faces.append((0, j + 1, j))
        last = (len(path) - 1) * sides
        faces.append((last, last + j, last + j + 1))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    finish(obj, parent, mat)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    # A stable cylindrical UV layout gives the weave a fine fabric appearance.
    uv = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex = mesh.loops[loop_index].vertex_index
            uv.data[loop_index].uv = ((vertex % sides) / sides * 2.0, (vertex // sides) / max(1, len(path)-1) * 4.0)
    obj.select_set(False)
    return obj


right = group("RightHandMesh")
rounded_box("RightPalm", (0.036, -0.083, 0.020), (0.033, 0.075, 0.050), right, fabric, 0.012, -0.18)
rounded_box("RightPalmReinforcement", (0.052, -0.079, 0.014), (0.005, 0.048, 0.035), right, rubber, 0.002)
for i, y in enumerate((-0.064, -0.082, -0.100)):
    z = -0.009 + i * 0.006
    tube("RightFinger" + str(i + 2), [(0.037, y, z), (0.029, y - .002, z - .018),
         (0.003, y - .002, z - .023), (-.019, y, z - .011), (-.021, y + .002, z + .004)],
         [0.008, 0.0077, 0.0067, 0.0055], right, fabric)
    rounded_box("RightKnucklePad" + str(i), (.041, y, z-.003), (.012, .012, .014), right, rubber, .004)
tube("RightIndex", [(.034,-.044,.005),(.029,-.043,-.022),(.025,-.046,-.047),
     (.013,-.050,-.061),(.004,-.051,-.060)], [.0078,.0075,.0065,.005], right, fabric)
tube("RightThumb", [(.029,-.068,.031),(.009,-.056,.029),(-.017,-.049,.016),
     (-.026,-.048,-.010)], [.0092,.0083,.0072,.0052], right, fabric)
tube("RightWrist", [(.039,-.112,.038),(.047,-.132,.057),(.059,-.150,.082)],
     [.019,.021,.023], right, fabric, flatten=.82)
tube("RightCuff", [(.055,-.144,.075),(.062,-.159,.093)], [.026,.026], right, cuff, flatten=.84)
tube("RightSleeve", [(.061,-.158,.092),(.086,-.205,.153),(.126,-.264,.225)],
     [.027,.031,.037], right, sleeve, flatten=.90)
tube("RightCuffSeam", [(.054,-.143,.078),(.059,-.148,.084)], [.0268,.0268], right, thread, flatten=.83)

left = group("LeftHandMesh")
rounded_box("LeftPalm", (-.036,-.092,.002), (.031,.061,.046), left, fabric, .012, -.25)
rounded_box("LeftPalmReinforcement", (-.051,-.093,.002), (.005,.040,.031), left, rubber, .002)
for i, y in enumerate((-.071,-.086,-.101,-.113)):
    r = .0072 if i < 3 else .006
    tube("LeftFinger" + str(i+1), [(-.047,y,-.010),(-.030,y,-.035),(-.006,y,-.043),
         (.021,y+.002,-.037),(.037,y+.005,-.020)], [r,r,.0063,.0048], left, fabric)
    rounded_box("LeftKnucklePad" + str(i),(-.044,y,-.012),(.012,.010,.014),left,rubber,.003)
tube("LeftThumb", [(-.034,-.067,.017),(-.035,-.047,-.003),(-.027,-.039,-.034),
     (-.025,-.037,-.065)], [.010,.009,.0076,.005], left, fabric)
tube("LeftWrist", [(-.042,-.115,.018),(-.055,-.138,.049),(-.067,-.159,.080)],
     [.019,.021,.024], left, fabric, flatten=.82)
tube("LeftCuff", [(-.062,-.151,.069),(-.071,-.168,.094)], [.027,.027], left, cuff, flatten=.84)
tube("LeftSleeve", [(-.069,-.166,.090),(-.100,-.215,.159),(-.143,-.274,.237)],
     [.028,.032,.037], left, sleeve, flatten=.90)
tube("LeftCuffSeam", [(-.060,-.148,.067),(-.064,-.155,.076)], [.0276,.0276], left, thread, flatten=.83)

for label, root in (("right", right), ("left", left)):
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for obj in root.children_recursive:
        obj.select_set(True)
    path = MODELS / ("fps_hands_" + label + ".glb")
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True,
        export_yup=True, export_apply=True, export_cameras=False, export_lights=False,
        export_materials="EXPORT", export_texcoords=True, export_normals=True,
        export_tangents=True)
    print("Exported", path)

scene = '''[gd_scene load_steps=3 format=3]

[ext_resource type="PackedScene" path="res://assets/models/fps_hands_right.glb" id="1_right"]
[ext_resource type="PackedScene" path="res://assets/models/fps_hands_left.glb" id="2_left"]

[node name="Hands" type="Node3D"]

[node name="RightHand" parent="." instance=ExtResource("1_right")]

[node name="LeftHand" parent="." instance=ExtResource("2_left")]
'''
(ROOT / "scenes" / "fps_hands.tscn").write_text(scene, encoding="utf-8")
print("Created posed hands; direct animation nodes: RightHand, LeftHand")
