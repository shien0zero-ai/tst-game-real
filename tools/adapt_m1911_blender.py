"""Fit the attributed, authored M1911 exterior to the game's stable viewmodel.

Run with Blender 4.3 or later:
    blender --background --factory-startup --python tools/adapt_m1911_blender.py

The source GLB contains the pistol only. This adapter preserves its materials,
UVs and authored normals, bakes its existing node transforms, and exports the
three separately animated exterior parts. It does not generate wear, add
bevels, import arms, or change the mesh shape. Attribution and source license
are recorded alongside the source asset and in the project's license files.
"""

import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "source_assets" / "m1911" / "m1911.glb"
OUTPUT = ROOT / "assets" / "models"
SCALE = 0.5
OFFSET = Vector((0.0, -0.041998953, -0.088))
PARTS = {
    "Body": "frame",
    "ChargingHandleGeometry": "slide",
    "MagazineGeometry": "magazine",
}


def godot_point(blender_point):
    """glTF/Godot +Y up, -Z forward from Blender +Z up."""
    return Vector((blender_point.x, blender_point.z, -blender_point.y))


def blender_point(godot_point_value):
    return Vector((godot_point_value.x, -godot_point_value.z, godot_point_value.y))


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(arguments)
    if not args.source.is_file():
        raise SystemExit(f"Missing authored gun-only source: {args.source}")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.source.resolve()),
                              import_pack_images=True, merge_vertices=False,
                              import_shading="NORMALS")
    bpy.context.view_layer.update()

    meshes = {obj.name: obj for obj in bpy.context.scene.objects if obj.type == "MESH"}
    if set(meshes) != set(PARTS):
        raise SystemExit(f"Expected only the three pistol exterior meshes; got {sorted(meshes)}")
    if any(obj.type == "ARMATURE" for obj in bpy.context.scene.objects):
        raise SystemExit("Gun-only source must not contain an armature")

    # Capture the complete author hierarchy before detaching each mesh. The
    # native prop is twice game scale; the fixed offset puts its muzzle socket
    # exactly on the established (0, .004, -.196) marker.
    native_world = {name: obj.matrix_world.copy() for name, obj in meshes.items()}
    muzzle = bpy.data.objects.get("MuzzleSocket")
    if muzzle is None:
        raise SystemExit("Missing source MuzzleSocket")
    muzzle_godot = godot_point(muzzle.matrix_world.translation) * SCALE + OFFSET
    if (muzzle_godot - Vector((0, .004, -.196))).length > 0.00001:
        raise SystemExit(f"Source muzzle changed: {tuple(muzzle_godot)}")
    fit = Matrix.Translation(blender_point(OFFSET)) @ Matrix.Scale(SCALE, 4)
    for name, obj in meshes.items():
        obj.parent = None
        obj.matrix_world = fit @ native_world[name]
        select_only(obj)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        if not obj.data.uv_layers or not all(poly.loop_total == 3 for poly in obj.data.polygons):
            raise SystemExit(f"Expected original triangulated UV mesh: {name}")

    # Empty attachment sockets are not part of the exported geometry. Existing
    # Godot wrapper nodes supply the animation pivots and muzzle marker.
    for obj in list(bpy.context.scene.objects):
        if obj.name not in meshes:
            bpy.data.objects.remove(obj, do_unlink=True)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, part in PARTS.items():
        obj = meshes[name]
        select_only(obj)
        path = args.output_dir / f"m1911_{part}.glb"
        bpy.ops.export_scene.gltf(filepath=str(path.resolve()), export_format="GLB",
                                  use_selection=True, export_yup=True,
                                  export_apply=False, export_texcoords=True,
                                  export_normals=True, export_tangents=True,
                                  export_materials="EXPORT", export_image_format="AUTO",
                                  export_animations=False, export_cameras=False,
                                  export_lights=False)
        points = [godot_point(vertex.co) for vertex in obj.data.vertices]
        minimum = [min(point[axis] for point in points) for axis in range(3)]
        maximum = [max(point[axis] for point in points) for axis in range(3)]
        print(f"EXPORTED {path.name}: {len(obj.data.polygons)} triangles; "
              f"Godot bounds {minimum} .. {maximum}")
    print(f"Fitted source muzzle: {tuple(muzzle_godot)}")
    print("Authored M1911 exterior adaptation complete; materials and topology retained.")


if __name__ == "__main__":
    main()
