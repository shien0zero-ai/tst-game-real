"""Fit the attributed, authored M1911 exterior to the game's stable viewmodel.

Run with Blender 4.3 or later:
    blender --background --factory-startup --python tools/adapt_m1911_blender.py

The source GLB contains the pistol only. This adapter preserves its UVs,
authored normals, base colors, occlusion and metalness, bakes its existing node
transforms, and exports the three separately animated exterior parts. It remaps
only the linear roughness channel for a worn satin finish, retaining the
artist's local surface variation. It does not generate wear, add bevels, import
arms, or change the mesh shape. Attribution and source license are recorded
alongside the source asset and in the project's license files.
"""

import argparse
from pathlib import Path
import sys

import bpy
import numpy as np
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


def upstream_images(socket, visited=None):
    """Find the imported packed ORM image feeding a roughness socket."""
    visited = set() if visited is None else visited
    images = {}
    for link in socket.links:
        node = link.from_node
        identity = node.as_pointer()
        if identity in visited:
            continue
        visited.add(identity)
        if node.type == "TEX_IMAGE" and node.image is not None:
            images[node.image.as_pointer()] = node.image
        else:
            for input_socket in node.inputs:
                images.update(upstream_images(input_socket, visited))
    return images


def apply_satin_roughness(materials):
    """Clone ORM maps and change G only; retain R/AO, B/metal and alpha."""
    original_images = {}
    for material in materials:
        for node in material.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                original_images.update(upstream_images(node.inputs["Roughness"]))
    if len(original_images) != 2:
        raise SystemExit(f"Expected two authored ORM maps, got {len(original_images)}")

    replacements = {}
    for identity, source in original_images.items():
        if source.colorspace_settings.name != "Non-Color":
            raise SystemExit(f"ORM must be linear data: {source.name}")
        pixels = np.empty(len(source.pixels), dtype=np.float32)
        source.pixels.foreach_get(pixels)
        if pixels.size != source.size[0] * source.size[1] * 4:
            raise SystemExit(f"Expected RGBA pixel buffer for {source.name}")
        pixels = pixels.reshape(-1, 4)
        before = pixels.copy()
        roughness = np.clip(before[:, 1], 0.0, 1.0)
        metalness = np.clip(before[:, 2], 0.0, 1.0)
        metal_weight = np.clip((metalness - .25) / (.85 - .25), 0.0, 1.0)
        metal_weight = metal_weight * metal_weight * (3.0 - 2.0 * metal_weight)
        satin_metal = np.maximum(.34, np.sqrt(roughness))
        oiled_wood = .08 + .92 * roughness
        adjusted = oiled_wood + (satin_metal - oiled_wood) * metal_weight
        # Quantize once to the same eight-bit data precision as the source.
        pixels[:, 1] = np.floor(np.clip(adjusted, 0.0, 1.0) * 255.0 + .5) / 255.0
        if not np.array_equal(pixels[:, (0, 2, 3)], before[:, (0, 2, 3)]):
            raise SystemExit(f"Satin finish altered non-roughness channels: {source.name}")
        image = bpy.data.images.new(source.name + "_satin_roughness",
                                   width=source.size[0], height=source.size[1],
                                   alpha=False, float_buffer=False, is_data=True)
        image.colorspace_settings.name = "Non-Color"
        image.file_format = "PNG"
        image.pixels.foreach_set(pixels.ravel())
        image.update()
        image.pack()
        replacements[identity] = image
        print(f"SATIN {source.name}: linear G remapped; R/B/A retained")

    # The imported AO and metallic/roughness nodes must share the same new map.
    for material in materials:
        for node in material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image is not None:
                replacement = replacements.get(node.image.as_pointer())
                if replacement is not None:
                    node.image = replacement


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
    materials = {material for obj in meshes.values() for material in obj.data.materials}
    apply_satin_roughness(materials)

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
    print("M1911 satin adaptation complete; only ORM roughness G changed, topology retained.")


if __name__ == "__main__":
    main()
