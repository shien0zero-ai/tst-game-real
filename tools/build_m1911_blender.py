"""Author an original, aged full-size early M1911 exterior game prop.

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
    if texture and texture.startswith("walnut"):
        # glTF COLOR_0 is a physical cavity/contact multiplier, not painted AO
        # around the whole weapon. Only tiny checker valleys are darkened.
        color = mat.node_tree.nodes.new("ShaderNodeVertexColor")
        color.layer_name = "SurfaceWear"
        mix = mat.node_tree.nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1
        source = shader.inputs["Base Color"].links[0].from_socket
        mat.node_tree.links.new(source,mix.inputs[1])
        mat.node_tree.links.new(color.outputs["Color"],mix.inputs[2])
        mat.node_tree.links.new(mix.outputs["Color"],shader.inputs["Base Color"])
    return mat


M = {
    "slide": material("Aged blue finish and recessed rollmarks", (1, 1, 1), .94, .43,
                       "slide" if (TEX / "weapon_slide_albedo.png").exists() else "steel", .65),
    "steel": material("Aged blue steel controls", (1, 1, 1), .94, .43, "steel", .35),
    "frame": material("Worn oxidized steel frame", (.85, .88, .87), .94, .45, "steel", .30),
    "frame_atlas": material("Continuous aged frame and recessed property stamp", (1,1,1), .94, .45,
                             "frame" if (TEX / "weapon_frame_albedo.png").exists() else "steel", .65),
    "edge": material("Rubbed exposed steel", (1, 1, 1), .97, .34,
                      "exposed" if (TEX / "weapon_exposed_albedo.png").exists() else "steel", .22),
    "barrel": material("Longitudinally brushed barrel", (1, 1, 1), .98, .262,
                       "brushed" if (TEX / "weapon_brushed_albedo.png").exists() else "steel", .20),
    "black": material("Darkened recesses and sights", (.008, .010, .009), .75, .51),
    "walnut": material("Dark oiled walnut", (1, 1, 1), 0, .45, "walnut", .35),
    "walnut_worn": material("Rubbed walnut tooth tips", (1, 1, 1), 0, .51,
                            "walnut_worn" if (TEX / "weapon_walnut_worn_albedo.png").exists() else "walnut", .35),
    "white": material("Aged ivory sight inserts", (.73, .75, .63), 0, .42),
}


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def uv_map(obj, wood=False, atlas=None):
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name="UVMap")
    uv = obj.data.uv_layers.active.data
    bpy.context.view_layer.update()
    for poly in obj.data.polygons:
        n = obj.matrix_world.to_3x3() @ poly.normal
        for li in poly.loop_indices:
            b = obj.matrix_world @ obj.data.vertices[obj.data.loops[li].vertex_index].co
            x, y, z = b.x, b.z, -b.y
            if atlas == "slide":
                # Six separate physical projections. The left slide strip is
                # reserved for properly located, shallow stamped rollmarks.
                a = min(1, max(0, (z+.182)/.187))
                b = min(1, max(0, (y+.014)/.02825))
                c = min(1, max(0, (x+.0128)/.0256))
                nx, ny, nz = n.x, n.z, -n.y
                if abs(nz) > max(abs(nx), abs(ny)):
                    coord = ((.02 if nz < 0 else .20)+.14*c, .86+.12*b)
                elif abs(ny) > abs(nx):
                    coord = (.02+.96*a,.70+.12*c) if ny >= 0 else (.38+.60*a,.86+.12*c)
                else:
                    coord = (.02+.96*a,(.02 if nx < 0 else .36)+.28*b)
            elif atlas == "frame":
                a = min(1,max(0,(z+.169)/.201))
                b = min(1,max(0,(y+.052)/.038))
                if abs(n.x) >= max(abs(n.y),abs(n.z)):
                    coord = (.02+.96*a,(.02 if n.x<0 else .52)+.44*b)
                else:
                    coord = (.02+.96*a,.47+.04*min(1,max(0,(x+.0125)/.025)))
            elif wood:
                coord = ((z + .0165) / .033, (y + .096) / .110)
            elif abs(n.y) > max(abs(n.x), abs(n.z)):
                coord = ((x + .014) / .028, (y + .018) / .033)
            elif abs(n.z) > abs(n.x):
                coord = ((-z + .010) / .195, (x + .014) / .028)
            else:
                coord = ((-z + .010) / .195, (y + .018) / .033)
            uv[li].uv = coord


def finish(obj, name, group, mat, bevel=.0003, segments=3, smooth=True,
           wood=False, edge=False, atlas=None, accent=None, accent_faces=()):
    obj.name = name
    obj.data.materials.clear()
    obj.data.materials.append(M[mat])
    if edge:
        obj.data.materials.append(M["edge"])
    if accent:
        obj.data.materials.append(M[accent])
        for index in accent_faces:
            obj.data.polygons[index].material_index = 1
    select_only(obj)
    uv_map(obj, wood, atlas)
    if wood and not obj.data.color_attributes:
        colors = obj.data.color_attributes.new(name="SurfaceWear",type="FLOAT_COLOR",domain="POINT")
        for color in colors.data:
            color.color = (1,1,1,1)
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


def union(obj, other):
    select_only(obj)
    mod = obj.modifiers.new("Continuous forged exterior", "BOOLEAN")
    mod.operation = "UNION"
    mod.solver = "EXACT"
    mod.object = other
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(other,do_unlink=True)


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
for i in range(1, 64):
    theta = pi-i*pi/64
    profile.append((.0128*cos(theta), min(.0013+.0131*sin(theta), .01425)))
profile += [(.0128, .0013), (.0128, -.014)]
slide = extrude("ForgedSlide", profile, .005, -.182, "z")
# Form the large exterior machining radii before any small cuts. Otherwise
# the close-set serrations clamp a whole-object bevel down to their spacing.
# The crown's small-angle curved segments are preserved; its front/rear ends
# and the hard lower longitudinal edges receive the visible 1.1 mm radius.
select_only(slide)
end_radius = slide.modifiers.new("Rounded forged slide ends", "BEVEL")
end_radius.width = .0011
end_radius.segments = 6
end_radius.limit_method = "ANGLE"
end_radius.angle_limit = radians(28)
bpy.ops.object.modifier_apply(modifier=end_radius.name)
difference(slide, cylinder_raw("Front barrel opening", .00945, .037, (0, .004, -.181)))
port = rounded_rectangle(.0145, -.070, .0120, .0170, .0025, 6)
difference(slide, extrude("Rounded ejection aperture", port, .0014, .025))
plate_profile = [(-.00615, -.0117), (-.00615, .0060), (-.0043, .0090),
                 (.0043, .0090), (.00615, .0060), (.00615, -.0117)]
pocket_profile = [(x*1.05,y*1.02) for x,y in plate_profile]
difference(slide, extrude("Rear plate pocket", pocket_profile, .0036, .0074, "z"))
for side in (-1, 1):
    for i in range(20):
        difference(slide, cube_raw("Fine vertical cocking serration", (.0012,.0185,.00044),
                                   (side*.0130,-.0032,-.0025-i*.00124)))
finish(slide, "ForgedSlide", "slide", "slide", .00012, 3, atlas="slide")
plate = extrude("FiringPinStopPlate", plate_profile, .0043, .0055, "z")
difference(plate, cylinder_raw("Firing pin recess", .00150, .004, (0, -.0012, .0056)))
finish(plate, "FiringPinStopPlate", "slide", "frame", .00012, 3)
cylinder("FiringPinRecess", "slide", "black", .00145, .0002, (0, -.0012, .0045), bevel=0)
cylinder("ExtractorRear", "slide", "steel", .00150, .00035, (.0089, .0025, .0052), bevel=.00008)
# Small plain GI notch and blade, without modern white inserts or a tall bridge.
# Aim through (0,.0172,-.0025) to the post top (0,.0172,-.1680).
sight_cross = [(-.0068,.0137),(-.0068,.0156),(-.0056,.0182),
               (-.00125,.0182),(-.00125,.0162),(.00125,.0162),
               (.00125,.0182),(.0056,.0182),(.0068,.0156),(.0068,.0137)]
finish(extrude("LowGIRearNotch",sight_cross,-.0050,-.0012,"z"),
       "LowGIRearNotch","slide","steel",.00012,3)
front_profile = [(.0140,-.1738),(.0140,-.1678),(.0172,-.1678),(.0172,-.1710)]
finish(extrude("PlainGIFrontBlade",front_profile,-.00085,.00085),
       "PlainGIFrontBlade","slide","steel",.00010,3)

# FRAME: one continuous forged side profile and rounded spring dust cover.
frame_side = [(-.0143,.006),(-.0143,-.166),(-.0210,-.166),
              (-.0225,-.152),(-.0230,-.100),(-.0230,-.075),
              (-.0240,-.053),(-.0280,-.038),(-.0360,-.024),
              (-.0350,-.012),(-.0290,.006)]
frame = extrude("SculptedFrame", frame_side, -.0125, .0125)
# Original M1911 has no A1 finger-relief scallops. The rounded dust-cover is
# actually united into the forging so its side has no rectangular block seam.
dust_profile = [(-.0125,-.0144),(-.0125,-.0200)]
for i in range(1, 18):
    t = pi+i*pi/18
    dust_profile.append((.0125*cos(t),-.0200+.0050*sin(t)))
dust_profile += [(.0125,-.0200),(.0125,-.0144)]
dust_sections = []
for z,sweep in ((-.169,0),(-.112,0),(-.096,.0003),(-.084,.0010),(-.073,.0023)):
    dust_sections.append([(x,y-sweep*max(0,(-.020-y)/.005),z) for x,y in dust_profile])
union(frame,loft("Swept rounded dust cover union",dust_sections))
finish(frame,"ContinuousForgedFrame","frame","frame_atlas",.00055,5,atlas="frame")
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

# Compact high oval guard with a real opening and long early solid trigger.
outer = closed_curve([(-.0225,-.0360),(-.0230,-.0680),(-.0285,-.0765),
                      (-.0370,-.0790),(-.0450,-.0758),(-.0502,-.0665),
                      (-.0512,-.0555),(-.0495,-.0455),(-.0435,-.0370),
                      (-.0300,-.0330)],12)
inner = closed_curve([(-.0262,-.0400),(-.0267,-.0665),(-.0310,-.0728),
                      (-.0373,-.0752),(-.0428,-.0725),(-.0463,-.0648),
                      (-.0474,-.0553),(-.0460,-.0472),(-.0411,-.0410),
                      (-.0313,-.0370)],12)
guard = extrude("OvalTriggerGuard", outer, -.0053, .0053)
difference(guard, extrude("Trigger guard aperture", inner, -.020, .020))
finish(guard,"HighRoundedOvalGuard","frame","frame_atlas",.00085,5,atlas="frame")
trigger_profile = closed_curve([(-.0240,-.0525),(-.0280,-.0550),(-.0340,-.0570),
                                (-.0400,-.0575),(-.0450,-.0555),(-.0470,-.0525),
                                (-.0455,-.0490),(-.0390,-.0520),(-.0320,-.0510),
                                (-.0260,-.0485)],5)
finish(extrude("LongSolidConcaveTrigger",trigger_profile,-.0047,.0047),
       "LongSolidConcaveTrigger","frame","steel",.00030,4)

# Cocked hammer: curved neck and small serrated spur; short rounded safety tang.
hammer_profile = closed_curve([(-.0225,.002),(-.014,-.001),(-.0065,.002),
                  (-.0015,.008),(.0020,.0134),(.0055,.0185),(.0080,.0214),
                  (.0085,.0230),(.0070,.0237),(.0050,.0232),(.0026,.0201),
                  (-.0015,.0144),(-.006,.0109),(-.0145,.0100),(-.022,.0095)],5)
finish(extrude("SlenderEarlySpurHammer",hammer_profile,-.0031,.0031),
       "SlenderEarlySpurHammer","frame","frame",.00030,4)
for i in range(7):
    z = .0150+i*.00115
    y = .0030+(z-.0150)*.62
    finish(cube_raw("HammerSpurSerration", (.0057, .00016, .00028), (0, y, z), -.42),
           "HammerSpurSerration", "frame", "black", .00005, 2)
tang_sections = []
for z, width, top, bottom in ((.005,.0060,-.0158,-.0236),
                              (.012,.0058,-.0166,-.0228),
                              (.018,.0048,-.0184,-.0223),
                              (.0205,.0040,-.0191,-.0220),
                              (.0215,.0035,-.0198,-.0217)):
    cy, hy = (top+bottom)/2, (top-bottom)/2
    tang_sections.append([(width*cos(i*2*pi/24),cy+hy*sin(i*2*pi/24),z)
                          for i in range(24)])
finish(loft("ShortRoundedGripSafetyTang", tang_sections),
       "ShortRoundedGripSafetyTang", "frame", "frame", .00025, 4)

# Shaped external controls, pins and finely textured small thumb pads.
stop = [(y+.004,z) for y,z in [(-.0220, -.063), (-.0218, -.057), (-.0235, -.050), (-.0230, -.037),
        (-.0254, -.034), (-.0283, -.036), (-.0282, -.049), (-.0270, -.061)]
       ]
finish(extrude("ProfiledSlideStopLever", stop, -.0147, -.0125),
       "ProfiledSlideStopLever", "frame", "steel", .00030, 3)
cylinder("SlideStopPivot", "frame", "steel", .00245, .0010, (-.0148, -.0210, -.060),
         (1, 0, 0), bevel=.00016)
for i in range(5):
    finish(cube_raw("SlideStopPadSerration", (.00015, .0038, .00028),
                    (-.01482, -.0217, -.0358-i*.0018)),
           "SlideStopPadSerration", "frame", "black", .00004, 2)
safety = [(y+.003,z) for y,z in [(-.0185, .003), (-.0194, -.006), (-.0220, -.012), (-.0254, -.010),
          (-.0265, .002), (-.0243, .008), (-.0214, .008)]]
finish(extrude("ThumbSafetyBody", safety, -.0148, -.0126),
       "ThumbSafetyBody", "frame", "frame", .00035, 4)
pad = [(y+.003,z) for y,z in [(-.0218, -.011), (-.0210, .0035), (-.0228, .0070),
       (-.0251, .0055), (-.0256, -.0085)]]
finish(extrude("ThumbSafetyPaddle", pad, -.0157, -.0136),
       "ThumbSafetyPaddle", "frame", "steel", .0004, 4)
for i in range(5):
    finish(cube_raw("SafetyPadSerration", (.0018, .00016, .00035),
                    (-.0148, -.0185, -.0072+i*.0024)),
           "SafetyPadSerration", "frame", "black", .00004, 2)
for label, side in (("L", -1), ("R", 1)):
    for i, (y, z, radius) in enumerate(((-.0175, .003, .0017),
                                      (-.0288, -.008, .00165), (-.033, .0045, .00115))):
        cylinder(f"FramePin{label}{i}", "frame", "steel", radius, .00055,
                 (side*.0128, y, z), (1, 0, 0), bevel=.00008)
finish(cylinder_raw("MagazineRelease", .00310, .0014, (-.0136, -.0320, -.0287), (1, 0, 0)),
       "MagazineRelease", "frame", "steel", .00018, 3)
for i in range(-2, 3):
    finish(cube_raw("MagazineCatchCheckering", (.00015, .0051, .00022),
                    (-.01435, -.0320, -.0287+i*.0010)),
           "MagazineCatchCheckering", "frame", "black", .00003, 2)
cylinder("MagazineCatchLock", "frame", "steel", .00255, .00065,
         (.0130, -.0320, -.0287), (1, 0, 0), bevel=.00012)

# GRIP: local to the established inclined wrapper. Changing cross-sections
# create rounded straps and a closely fitted 31.5 mm panel-to-panel width.
sections = []
for y, hz, zc, hx in ((.007,.0118,0,.0123),(-.001, .0152, .001, .0125), (-.016, .0171, 0, .0130),
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
for y, back in ((-.034,.0172),(-.050,.0174),(-.070,.0172),(-.086,.0158),(-.095,.0136)):
    section = []
    for i in range(43):
        x = -.0105+.021*i/42
        crown = .00045*(1-(x/.0105)**2)
        groove = .00012*(.5+.5*cos(x/.0010*2*pi))
        section.append((x,y,back+crown-groove))
    section += [(.0105,y,back-.0028), (-.0105,y,back-.0028)]
    housing_sections.append(section)
finish(loft("FlatEarlyMainspringHousing", housing_sections),
       "FlatEarlyMainspringHousing", "grip", "steel", .00008, 2)
safety_sections = []
for y, back, width in ((.009,.0125,.0085),(-.006,.0165,.0092),
                        (-.024,.0173,.0091),(-.037,.0172,.0090)):
    safety_sections.append([(-width,y,back-.002), (-width,y,back),
                            (0,y,back+.0008), (width,y,back), (width,y,back-.002)])
finish(loft("UpperGripSafetyBackstrap", safety_sections),
       "UpperGripSafetyBackstrap", "grip", "frame", .0003, 3)
cylinder("HousingPin", "grip", "steel", .00155, .0240,
         (0,-.0895,.007), (1,0,0), bevel=.00010)

# A small exterior lanyard staple sits at the lower rear of the flat housing.
loop_vertices,loop_faces = [],[]
for i in range(48):
    t = 2*pi*i/48
    for j in range(12):
        p = 2*pi*j/12
        loop_vertices.append(((.0043+.00075*cos(p))*cos(t),
                              -.0965+(.0034+.00075*cos(p))*sin(t),
                              .0155+.00075*sin(p)))
for i in range(48):
    for j in range(12):
        loop_faces.append((i*12+j,i*12+(j+1)%12,((i+1)%48)*12+(j+1)%12,((i+1)%48)*12+j))
finish(mesh_object("SmallLanyardLoop",loop_vertices,loop_faces),
       "SmallLanyardLoop","grip","steel",0)

# The reference has a tall fitted panel. Upper wood and the upper screw move
# up substantially; the lower end and existing magazine pivot remain fixed.
panel_outline = closed_curve([(.013,-.0105),(.0108,.003),(.004,.0125),
                              (-.018,.0160),(-.064,.0157),(-.088,.0128),
                              (-.095,.004),(-.093,-.0105),(-.083,-.0148),
                              (-.030,-.0158),(.006,-.0135)],8)
panel_outline = [(min(.014,max(-.096,y)),min(.0165,max(-.0165,z))) for y,z in panel_outline]
panel_center_y = -.041
flat_outline = [(panel_center_y+(y-panel_center_y)*.935,z*.935) for y,z in panel_outline]
SCREW_Y = (-.0815,.0002)


def inside_panel(y, z, margin=0):
    inside = False
    p = Vector((y,z))
    for i,a in enumerate(flat_outline):
        b = flat_outline[(i+1)%len(flat_outline)]
        if (a[1]>z) != (b[1]>z) and y < (b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
        av,bv = Vector(a),Vector(b)
        delta = bv-av
        t = min(1,max(0,(p-av).dot(delta)/max(delta.length_squared,1e-12)))
        if (p-(av+t*delta)).length < margin:
            return False
    return inside


for label, side in (("Left",-1), ("Right",1)):
    rings = []
    for scale,x in ((1,.0128),(1,.0134),(.985,.0143),(.955,.0152),(.935,.0156)):
        rings.append([(side*x,panel_center_y+(y-panel_center_y)*scale,z*scale) for y,z in panel_outline])
    panel = loft(label+"CrownedWalnutPanel", rings)
    for y in SCREW_Y:
        difference(panel, cylinder_raw("Grip screw seat", .00335, .008,
                                      (side*.0160,y,0), (1,0,0)))
    finish(panel,label+"FittedTaperedWalnutPanel","grip","walnut",.00008,3,wood=True)
    verts,faces,wear_faces,vertex_shade = [],[],[],[]
    pitch = .00122
    for row in range(172):
        y = -.092+row*pitch/2
        for col in range(29):
            z = -.017+col*pitch+(row%2)*pitch/2
            corners = [(y-pitch/2,z),(y,z+pitch/2),(y+pitch/2,z),(y,z-pitch/2)]
            if not all(inside_panel(a,b,.00025) for a,b in corners):
                continue
            if any(abs(y-sy)/.0105+abs(z)/.0072 < 1.08 for sy in SCREW_Y):
                continue
            n = len(verts)
            verts += [(side*.01563,a,b) for a,b in corners]
            vertex_shade += [.58]*4
            contact = .40 if -.077<y<-.005 and z<.004 else .16
            hashed = ((row*1103515245+col*12345+(side+2)*1957)&65535)/65535
            if hashed < contact:
                verts += [(side*.01570,y+(a-y)*.20,z+(b-z)*.20) for a,b in corners]
                vertex_shade += [1]*4
                faces += [(n+i,n+(i+1)%4,n+4+(i+1)%4,n+4+i) for i in range(4)]
                wear_faces.append(len(faces))
                faces.append((n+4,n+5,n+6,n+7))
            else:
                verts.append((side*.01575,y,z))
                vertex_shade.append(1)
                faces += [(n+i,n+(i+1)%4,n+4) for i in range(4)]
    checker = mesh_object(label+"ContactWornFineCheckering",verts,faces)
    colors = checker.data.color_attributes.new(name="SurfaceWear",type="FLOAT_COLOR",domain="POINT")
    for color,shade in zip(colors.data,vertex_shade):
        color.color = (shade,shade,shade,1)
    finish(checker,label+"ContactWornFineCheckering","grip","walnut",0,
           smooth=False,wood=True,accent="walnut_worn",accent_faces=wear_faces)
    for i,y in enumerate(SCREW_Y):
        screw = cylinder_raw(label+"SlottedGripScrew", .00275, .00135,
                             (side*.01525,y,0), (1,0,0))
        difference(screw,cube_raw("Shallow diagonal driver slot",(.0008,.00065,.0048),
                                  (side*.01585,y,0),radians(23)))
        finish(screw, label+f"SlottedGripScrew{i}", "grip", "steel", .00010, 3, edge=True)
        finish(cylinder_raw(label+"GripScrewSeat", .00332, .00020,
                             (side*.0147,y,0), (1,0,0)),
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
                              export_vertex_color="ACTIVE",
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
print("Reference-shaped worn early M1911 exterior export completed.")
