"""Author an original, reference-proportioned M1911A1 exterior game prop.

Only exterior surfaces are modelled; no mechanical assemblies or working
internals. Metres, Godot -Z forward/+Y up. Four exports retain the established
animation wrappers. Run with M1911_PREVIEW=1 for untracked authoring renders.
"""
from pathlib import Path
from math import cos, sin, pi, sqrt, radians
import os
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "models"
TEX = ROOT / "assets" / "textures"
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = "METRIC"
PARTS = {name: [] for name in ("slide", "frame", "grip", "magazine")}


def point(g):
    return Vector((g[0], -g[2], g[1]))


def material(name, color, metal, roughness, texture=None, normal_strength=.1):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metal
    shader.inputs["Roughness"].default_value = roughness
    if texture:
        for suffix, socket in (("albedo", "Base Color"), ("roughness", "Roughness"),
                               ("normal", None)):
            path = TEX / f"weapon_{texture}_{suffix}.png"
            if not path.exists():
                continue
            image = bpy.data.images.load(str(path), check_existing=True)
            if suffix != "albedo":
                image.colorspace_settings.name = "Non-Color"
            node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = image
            if suffix == "normal":
                normal = mat.node_tree.nodes.new("ShaderNodeNormalMap")
                normal.inputs["Strength"].default_value = normal_strength
                mat.node_tree.links.new(node.outputs["Color"], normal.inputs["Color"])
                mat.node_tree.links.new(normal.outputs["Normal"], shader.inputs["Normal"])
            else:
                mat.node_tree.links.new(node.outputs["Color"], shader.inputs[socket])
    return mat


M = {
    "steel": material("Satin blued slide", (1, 1, 1), .94, .415, "steel", .16),
    "frame": material("Satin blued frame", (.85, .88, .87), .94, .44, "steel", .12),
    "edge": material("Subtle burnished steel edges", (.095, .104, .099), .96, .31),
    "barrel": material("Longitudinally brushed barrel", (1, 1, 1), .98, .262,
                       "brushed" if (TEX / "weapon_brushed_albedo.png").exists() else "steel", .20),
    "black": material("Darkened recesses and sights", (.008, .010, .009), .75, .51),
    "walnut": material("Dark oiled walnut", (1, 1, 1), 0, .45, "walnut", .35),
    "white": material("Aged ivory sight inserts", (.73, .75, .63), 0, .42),
}


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def uv_map(obj, wood=False):
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name="UVMap")
    uv = obj.data.uv_layers.active.data
    bpy.context.view_layer.update()
    for poly in obj.data.polygons:
        n = obj.matrix_world.to_3x3() @ poly.normal
        for li in poly.loop_indices:
            b = obj.matrix_world @ obj.data.vertices[obj.data.loops[li].vertex_index].co
            x, y, z = b.x, b.z, -b.y
            if wood:
                coord = ((z + .014) / .028, (y + .091) / .083)
            elif abs(n.y) > max(abs(n.x), abs(n.z)):
                coord = ((x + .014) / .028, (y + .018) / .033)
            elif abs(n.z) > abs(n.x):
                coord = ((-z + .010) / .195, (x + .014) / .028)
            else:
                coord = ((-z + .010) / .195, (y + .018) / .033)
            uv[li].uv = coord


def finish(obj, name, group, mat, bevel=.0003, segments=3, smooth=True,
           wood=False, edge=False):
    obj.name = name
    obj.data.materials.clear()
    obj.data.materials.append(M[mat])
    if edge:
        obj.data.materials.append(M["edge"])
    select_only(obj)
    uv_map(obj, wood)
    if bevel:
        mod = obj.modifiers.new("Small machined edge radius", "BEVEL")
        mod.width = bevel
        mod.segments = segments
        mod.limit_method = "ANGLE"
        mod.angle_limit = radians(28)
        mod.harden_normals = True
        if edge:
            mod.material = 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
        obj.data.set_sharp_from_angle(angle=radians(38))
        weighted = obj.modifiers.new("Machined flat face normals", "WEIGHTED_NORMAL")
        weighted.keep_sharp = True
        weighted.weight = 50
        bpy.ops.object.modifier_apply(modifier=weighted.name)
    tri = obj.modifiers.new("Stable tangent triangles", "TRIANGULATE")
    if hasattr(tri, "keep_custom_normals"):
        tri.keep_custom_normals = True
    bpy.ops.object.modifier_apply(modifier=tri.name)
    if group:
        PARTS[group].append(obj)
    return obj


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


def extrude(name, profile, a, b, axis="x"):
    n = len(profile)
    if axis == "x":
        verts = [(x, y, z) for x in (a, b) for y, z in profile]
    else:
        verts = [(x, y, z) for z in (a, b) for x, y in profile]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, n * 2))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    return mesh_object(name, verts, faces)


def rounded_rectangle(cy, cz, hy, hz, radius, steps=6):
    p = []
    for y, z, angle in ((cy + hy - radius, cz + hz - radius, 0),
                        (cy - hy + radius, cz + hz - radius, 90),
                        (cy - hy + radius, cz - hz + radius, 180),
                        (cy + hy - radius, cz - hz + radius, 270)):
        for i in range(steps + 1):
            t = radians(angle + i * 90 / steps)
            p.append((y + radius * cos(t), z + radius * sin(t)))
    return p


def closed_curve(points, steps=8):
    """Interpolated side silhouette, avoiding a polygonal/boxy guard loop."""
    result = []
    for i in range(len(points)):
        a,b,c,d = [Vector(points[j % len(points)]) for j in (i-1,i,i+1,i+2)]
        for k in range(steps):
            t = k/steps
            p = .5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)
            result.append(tuple(p))
    return result


def cube_raw(name, size, pos, angle=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=point(pos))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (size[0], size[2], size[1])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler.x = angle
    return obj


def cylinder_raw(name, radius, depth, pos, axis=(0, 0, 1), vertices=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                       depth=depth, location=point(pos))
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(point(axis).normalized())
    return obj


def cylinder(name, group, mat, radius, depth, pos, axis=(0, 0, 1), bevel=.00012):
    return finish(cylinder_raw(name, radius, depth, pos, axis), name, group, mat, bevel)


def difference(obj, cutter):
    select_only(obj)
    mod = obj.modifiers.new("Exterior machined opening", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def ring(name, group, mat, outer, inner, depth, pos):
    obj = cylinder_raw(name, outer, depth, pos)
    difference(obj, cylinder_raw("Exterior bore cutter", inner, depth * 3, pos))
    return finish(obj, name, group, mat, .00010, 3, edge=mat != "black")


def loft(name, sections):
    n = len(sections[0])
    verts = [v for section in sections for v in section]
    faces = [tuple(range(n - 1, -1, -1))]
    for j in range(len(sections) - 1):
        faces += [(j*n+i, j*n+(i+1)%n, (j+1)*n+(i+1)%n, (j+1)*n+i)
                  for i in range(n)]
    faces.append(tuple(range((len(sections)-1)*n, len(sections)*n)))
    return mesh_object(name, verts, faces)


# SLIDE: 25.6 mm width, 28.4 mm height. The bore sits near the crown, rather
# than under the large blank semicircular arch of the previous prop.
profile = [(-.0128, -.014), (-.0128, .0013)]
for i in range(1, 32):
    theta = pi-i*pi/32
    profile.append((.0128*cos(theta), min(.0013+.0131*sin(theta), .01425)))
profile += [(.0128, .0013), (.0128, -.014)]
slide = extrude("ForgedSlide", profile, .005, -.182, "z")
difference(slide, cylinder_raw("Front barrel opening", .00945, .037, (0, .004, -.181)))
port = rounded_rectangle(.0145, -.070, .0120, .0170, .0025, 6)
difference(slide, extrude("Rounded ejection aperture", port, .0014, .025))
plate_profile = [(-.00615, -.0117), (-.00615, .0060), (-.0043, .0090),
                 (.0043, .0090), (.00615, .0060), (.00615, -.0117)]
pocket_profile = [(x*1.05,y*1.02) for x,y in plate_profile]
difference(slide, extrude("Rear plate pocket", pocket_profile, .0036, .0074, "z"))
for side in (-1, 1):
    for i in range(7):
        difference(slide, cube_raw("Cocking serration", (.0020, .0185, .00105),
                                   (side*.0129, -.0032, .0008-i*.00355), radians(8)))
finish(slide, "ForgedSlide", "slide", "steel", .00022, 3, edge=True)
plate = extrude("FiringPinStopPlate", plate_profile, .0043, .0055, "z")
difference(plate, cylinder_raw("Firing pin recess", .00150, .004, (0, -.0012, .0056)))
finish(plate, "FiringPinStopPlate", "slide", "frame", .00012, 3)
cylinder("FiringPinRecess", "slide", "black", .00145, .0002, (0, -.0012, .0045), bevel=0)
cylinder("ExtractorRear", "slide", "steel", .00150, .00035, (.0089, .0025, .0052), bevel=.00008)
# One low machined sight bridge with a U notch, preserving X while lowering Y.
sight_cross = [(-.0117, .0135), (-.0117, .0172), (-.0105, .0230),
               (-.0047, .0240), (-.0047, .0183), (.0047, .0183),
               (.0047, .0240), (.0105, .0230), (.0117, .0172), (.0117, .0135)]
finish(extrude("NotchedRearSight", sight_cross, -.0075, .0002, "z"),
       "NotchedRearSight", "slide", "black", .00018, 3)
for side in (-1, 1):
    cylinder("RearSightInsertL" if side < 0 else "RearSightInsertR", "slide", "white",
             .00105, .00025, (side*.0085, .0208, .00034), bevel=.00006)
front_profile = [(.0134, -.176), (.0134, -.161), (.0200, -.162),
                 (.0210, -.165), (.0210, -.174)]
finish(extrude("RampedFrontSight", front_profile, -.0019, .0019),
       "RampedFrontSight", "slide", "black", .00016, 3)
cylinder("FrontSightInsert", "slide", "white", .0010, .00025, (0, .0186, -.1619), bevel=.00005)

# FRAME: forged side profile and a separate rounded recoil-spring dust cover.
frame_side = [(-.0143, .006), (-.0143, -.118), (-.0270, -.118),
              (-.0287, -.108), (-.0298, -.097), (-.0296, -.089), (-.0290, -.076),
              (-.0320, -.049), (-.0470, -.033), (-.0520, -.018),
              (-.0410, .006), (-.0300, .010)]
frame = extrude("SculptedFrame", frame_side, -.0125, .0125)
for side in (-1, 1):
    difference(frame, cylinder_raw("A1 finger relief", .013, .004,
                                   (side*.0132, -.0440, -.0270), (1, 0, 0)))
finish(frame, "SculptedFrame", "frame", "frame", .0005, 4, edge=True)
dust_profile = [(-.0116, -.0144), (-.0116, -.0235)]
for i in range(1, 18):
    t = pi+i*pi/18
    dust_profile.append((.0116*cos(t), -.0235+.0065*sin(t)))
dust_profile += [(.0116, -.0235), (.0116, -.0144)]
finish(extrude("RoundedDustCover", dust_profile, -.093, -.169, "z"),
       "RoundedDustCover", "frame", "frame", .00035, 3, edge=True)
for side in (-1, 1):
    finish(cube_raw("SlideFrameClearance", (.00018, .00055, .159),
                    (side*.01265, -.01415, -.074)),
           "SlideFrameClearance", "frame", "black", 0, smooth=False)
cylinder("BarrelVisibleAtPort", "frame", "barrel", .00815, .139,
         (0, .004, -.1150), bevel=.00015)
hood = extrude("ChamberHood", rounded_rectangle(.0110, -.065, .0024, .016, .0012),
               -.0061, .0061)
finish(hood, "ChamberHood", "frame", "barrel", .00016, 3)
ring("BarrelBushingFlange", "frame", "steel", .01105, .00875, .0025, (0, .004, -.1832))
ring("BushingCollar", "frame", "barrel", .00880, .00805, .0040, (0, .004, -.184))
ring("RecessedMuzzleCrown", "frame", "barrel", .00812, .00565, .0040, (0, .004, -.1855))
ring("DarkBoreWall", "frame", "black", .00567, .00550, .011, (0, .004, -.182))
cylinder("DeepBoreOcclusion", "frame", "black", .00551, .0003, (0, .004, -.175), bevel=0)
cylinder("RecoilSpringPlug", "frame", "steel", .00565, .0040, (0, -.0140, -.1820), bevel=.00022)
for i in range(-4, 5):
    width = 2*sqrt(max(0, .0050**2-(i*.0010)**2))
    finish(cube_raw("PlugFaceSerration", (width, .00013, .00008),
                    (0, -.0140+i*.0010, -.18404)),
           "PlugFaceSerration", "frame", "black", 0, smooth=False)

# Thin oval guard with a real opening and short, solid curved A1 trigger.
outer = closed_curve([(-.0315,-.0385),(-.0317,-.075),(-.0360,-.0850),
                      (-.0570,-.0860),(-.0665,-.0775),(-.0675,-.0470),
                      (-.0605,-.0365),(-.0420,-.0348)])
inner = closed_curve([(-.0367,-.0430),(-.0369,-.0735),(-.0400,-.0805),
                      (-.0552,-.0810),(-.0619,-.0750),(-.0627,-.0485),
                      (-.0570,-.0420),(-.0430,-.0405)])
guard = extrude("OvalTriggerGuard", outer, -.0053, .0053)
difference(guard, extrude("Trigger guard aperture", inner, -.020, .020))
finish(guard, "OvalTriggerGuard", "frame", "frame", .00065, 4, edge=True)
trigger_profile = [(-.0328, -.0440), (-.0370, -.0454), (-.0430, -.0474),
                   (-.0490, -.0480), (-.0540, -.0466), (-.0570, -.0440),
                   (-.0560, -.0418), (-.0500, -.0428), (-.0430, -.0431), (-.0365, -.0415)]
finish(extrude("ShortCurvedTrigger", trigger_profile, -.0049, .0049),
       "ShortCurvedTrigger", "frame", "steel", .00045, 4, edge=True)
for i in range(7):
    finish(cube_raw("TriggerFaceFineSerration", (.0090, .00020, .00018),
                    (0, -.0365-i*.0026, -.0450-.0026*sin(i*pi/6))),
           "TriggerFaceFineSerration", "frame", "black", .00004, 2)

# Cocked hammer: curved neck and small serrated spur; short rounded safety tang.
hammer_profile = [(-.0220,.002), (-.0140,-.001), (-.0060,.002),
                  (-.0010,.008), (.0020,.014), (.0036,.021), (.0040,.025),
                  (.0032,.028), (.0018,.029), (0,.0295), (-.0018,.0285),
                  (-.0030,.025), (-.0048,.019), (-.0090,.014),
                  (-.0160,.012), (-.0220,.011)]
finish(extrude("CurvedSpurHammer", hammer_profile, -.0036, .0036),
       "CurvedSpurHammer", "frame", "frame", .00045, 4, edge=True)
for i in range(6):
    z = .0160+i*.00175
    y = .0033+.0004*sin((z-.016)/.011*pi)
    finish(cube_raw("HammerSpurSerration", (.0066, .00020, .00032), (0, y, z), -.15),
           "HammerSpurSerration", "frame", "black", .00005, 2)
tang_sections = []
for z, width, top, bottom in ((.006,.0073,-.0178,-.0340),
                              (.015,.0071,-.0188,-.0290),
                              (.023,.0066,-.0209,-.0258),
                              (.0285,.0050,-.0223,-.0252),
                              (.0305,.0025,-.0230,-.0248),
                              (.0310,.0007,-.0235,-.0243)):
    cy, hy = (top+bottom)/2, (top-bottom)/2
    tang_sections.append([(width*cos(i*2*pi/24),cy+hy*sin(i*2*pi/24),z)
                          for i in range(24)])
finish(loft("ShortRoundedGripSafetyTang", tang_sections),
       "ShortRoundedGripSafetyTang", "frame", "frame", .0001, 3)

# Shaped external controls, pins and finely textured small thumb pads.
stop = [(-.0220, -.063), (-.0218, -.057), (-.0235, -.050), (-.0230, -.037),
        (-.0254, -.034), (-.0283, -.036), (-.0282, -.049), (-.0270, -.061)]
finish(extrude("ProfiledSlideStopLever", stop, -.0160, -.0127),
       "ProfiledSlideStopLever", "frame", "steel", .00030, 3)
cylinder("SlideStopPivot", "frame", "steel", .00265, .0014, (-.0160, -.0250, -.060),
         (1, 0, 0), bevel=.00016)
for i in range(5):
    finish(cube_raw("SlideStopPadSerration", (.00015, .0038, .00028),
                    (-.0161, -.0257, -.0358-i*.0018)),
           "SlideStopPadSerration", "frame", "black", .00004, 2)
safety = [(-.0185, .003), (-.0194, -.006), (-.0220, -.012), (-.0254, -.010),
          (-.0265, .002), (-.0243, .008), (-.0214, .008)]
finish(extrude("ThumbSafetyBody", safety, -.0148, -.0126),
       "ThumbSafetyBody", "frame", "frame", .00035, 4)
pad = [(-.0218, -.011), (-.0210, .0035), (-.0228, .0070),
       (-.0251, .0055), (-.0256, -.0085)]
finish(extrude("ThumbSafetyPaddle", pad, -.0186, -.0136),
       "ThumbSafetyPaddle", "frame", "steel", .0004, 4)
for i in range(5):
    finish(cube_raw("SafetyPadSerration", (.0040, .00016, .00035),
                    (-.0165, -.0215, -.0072+i*.0024)),
           "SafetyPadSerration", "frame", "black", .00004, 2)
for label, side in (("L", -1), ("R", 1)):
    for i, (y, z, radius) in enumerate(((-.0175, .003, .0017),
                                      (-.0288, -.008, .00165), (-.033, .0045, .00115))):
        cylinder(f"FramePin{label}{i}", "frame", "steel", radius, .00055,
                 (side*.0128, y, z), (1, 0, 0), bevel=.00008)
finish(cylinder_raw("MagazineRelease", .00345, .0018, (-.0140, -.0415, -.0287), (1, 0, 0)),
       "MagazineRelease", "frame", "steel", .00018, 3)
for i in range(-2, 3):
    finish(cube_raw("MagazineCatchCheckering", (.00015, .0051, .00022),
                    (-.0150, -.0415, -.0287+i*.0010)),
           "MagazineCatchCheckering", "frame", "black", .00003, 2)
cylinder("MagazineCatchLock", "frame", "steel", .00255, .00065,
         (.0130, -.0415, -.0287), (1, 0, 0), bevel=.00012)

# GRIP: local to the established inclined wrapper. Changing cross-sections
# create rounded front/back straps and a slimmer 34.2 mm panel-to-panel width.
sections = []
for y, hz, zc, hx in ((-.001, .0152, .001, .0125), (-.016, .0171, 0, .0130),
                       (-.043, .0172, .0005, .0130), (-.074, .0165, .001, .0127),
                       (-.092, .0144, .0005, .0121), (-.096, .0133, -.0003, .0115)):
    section = []
    for i in range(48):
        t = 2*pi*i/48
        x = hx*(1 if cos(t)>=0 else -1)*abs(cos(t))**.58
        z = zc+hz*(1 if sin(t)>=0 else -1)*abs(sin(t))**.58
        section.append((x,y,z))
    sections.append(section)
finish(loft("ContouredGripFrame", sections), "ContouredGripFrame", "grip", "frame", .00020, 3)
housing_sections = []
for y, back in ((-.034, .0179), (-.044, .0205), (-.057, .0225),
                 (-.071, .0228), (-.084, .0201), (-.094, .0144)):
    section = []
    for i in range(43):
        x = -.0105+.021*i/42
        crown = .0015*(1-(x/.0105)**2)
        groove = .00012*(.5+.5*cos(x/.0010*2*pi))
        section.append((x,y,back+crown-groove))
    section += [(.0105,y,back-.0028), (-.0105,y,back-.0028)]
    housing_sections.append(section)
finish(loft("ArchedSerratedMainspringHousing", housing_sections),
       "ArchedSerratedMainspringHousing", "grip", "steel", .00008, 2)
safety_sections = []
for y, back, width in ((-.001, .0160, .0100), (-.012, .0190, .0105),
                        (-.025, .0190, .0104), (-.035, .0180, .0101)):
    safety_sections.append([(-width,y,back-.002), (-width,y,back),
                            (0,y,back+.0013), (width,y,back), (width,y,back-.002)])
finish(loft("UpperGripSafetyBackstrap", safety_sections),
       "UpperGripSafetyBackstrap", "grip", "frame", .0003, 3)
cylinder("HousingPin", "grip", "steel", .00155, .0240,
         (0,-.0895,.007), (1,0,0), bevel=.00010)

panel_outline = rounded_rectangle(-.0495, 0, .0415, .014, .0060, 12)


def inside_panel(y, z, margin=0):
    a = abs(y+.0495)-(.0355-.0048-margin)
    b = abs(z)-(.0118-.0048-margin)
    return max(a,0)**2+max(b,0)**2 < (.0048-margin)**2


for label, side in (("Left",-1), ("Right",1)):
    rings = []
    for scale, x in ((1,.0131), (1,.01425), (.974,.01535), (.906,.01655), (.862,.01695)):
        rings.append([(side*x,-.0495+(y+.0495)*scale,z*scale) for y,z in panel_outline])
    panel = loft(label+"CrownedWalnutPanel", rings)
    for y in (-.07772,-.02128):
        difference(panel, cylinder_raw("Grip screw seat", .00335, .008,
                                      (side*.0176,y,0), (1,0,0)))
    finish(panel, label+"CrownedWalnutPanel", "grip", "walnut", .00012, 3, wood=True)
    verts, faces = [], []
    pitch = .00122
    for row in range(130):
        y = -.0885+row*pitch/2
        for col in range(24):
            z = -.014+col*pitch+(row%2)*pitch/2
            corners = [(y-pitch/2,z),(y,z+pitch/2),(y+pitch/2,z),(y,z-pitch/2)]
            if not all(inside_panel(a,b,.00025) for a,b in corners):
                continue
            if any(abs(y-sy)/.0090+abs(z)/.0074 < 1.10 for sy in (-.07772,-.02128)):
                continue
            n = len(verts)
            verts += [(side*.01698,a,b) for a,b in corners]
            verts.append((side*.01710,y,z))
            faces += [(n+i,n+(i+1)%4,n+4) for i in range(4)]
    finish(mesh_object(label+"FineDiamondCheckering",verts,faces),
           label+"FineDiamondCheckering", "grip", "walnut", 0, smooth=False, wood=True)
    for i,y in enumerate((-.07772,-.02128)):
        screw = cylinder_raw(label+"SlottedGripScrew", .00275, .00135,
                             (side*.01645,y,0), (1,0,0))
        difference(screw, cube_raw("Diagonal driver slot", (.006,.00065,.0045),
                                   (side*.0171,y,0), radians(23)))
        finish(screw, label+f"SlottedGripScrew{i}", "grip", "steel", .00010, 3, edge=True)
        finish(cylinder_raw(label+"GripScrewSeat", .00332, .00020,
                             (side*.0155,y,0), (1,0,0)),
               label+f"GripScrewSeat{i}", "grip", "black", .00005, 2)

# Thin rounded magazine floor plate, independent for the existing reload pose.
base_profile = rounded_rectangle(0,0,.0021,.0174,.0018,8)
finish(extrude("ThinMagazineFloorplate",base_profile,-.0141,.0141),
       "ThinMagazineFloorplate", "magazine", "steel", .00025, 3, edge=True)
wall_profile = rounded_rectangle(.0063,-.0003,.0063,.0124,.0018,6)
finish(extrude("MagazineLowerWall",wall_profile,-.0108,.0108),
       "MagazineLowerWall", "magazine", "frame", .00025, 3)

for group,objects in PARTS.items():
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    path = OUT/f"m1911_{group}.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_texcoords=True,
                              export_normals=True, export_tangents=True,
                              export_materials="EXPORT", export_image_format="AUTO")
    print(f"Exported {path.name}: {len(objects)} exterior parts; "
          f"{sum(len(o.data.polygons) for o in objects)} triangles")


def preview():
    for name,loc in (("grip",(0,-.029,-.009)), ("magazine",(0,-.123,.019))):
        matrix = Matrix.Translation(point(loc)) @ Euler((-.296706,0,0)).to_matrix().to_4x4()
        for obj in PARTS[name]:
            obj.matrix_world = matrix @ obj.matrix_world
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.world.color = (.18,.18,.18)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -3.0
    target = point((0,-.035,-.07))
    for name,pos,power,size in (("Large softbox",(.20,.30,-.05),35,.30),
                               ("Long reflection",(-.20,.12,-.12),25,.25),
                               ("Rim strip",(.07,.05,.22),18,.16)):
        bpy.ops.object.light_add(type="AREA", location=point(pos))
        light = bpy.context.object
        light.name = name
        light.data.energy = power
        light.data.shape = "DISK"
        light.data.size = size
        light.rotation_euler = (target-light.location).to_track_quat("-Z","Y").to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = .31
    scene.camera = camera
    camera.location = point((-.34,.19,.35))
    camera.rotation_euler = (target-camera.location).to_track_quat("-Z","Y").to_euler()
    work = ROOT.parent/"work"/"weapon-model"
    work.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(work/"m1911-exterior-preview.blend"))
    for name,pos in (("threequarter",(-.34,.19,.35)), ("side",(-.38,.015,-.05)),
                      ("rear",(-.10,.11,.32)), ("muzzle",(-.12,.09,-.38))):
        camera.location = point(pos)
        camera.rotation_euler = (target-camera.location).to_track_quat("-Z","Y").to_euler()
        scene.render.filepath = str(work/f"m1911-{name}.png")
        bpy.ops.render.render(write_still=True)


if os.environ.get("M1911_PREVIEW") == "1":
    preview()
print("Reference-proportioned M1911A1 exterior export completed.")
