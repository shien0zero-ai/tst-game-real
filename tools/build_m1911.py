#!/usr/bin/env python3
"""Regenerate the original bevelled M1911 exterior and its Godot wrapper.

Requires Blender 4.3+, NumPy and Pillow on the asset-authoring machine only.
The shipped game uses the generated GLBs and does not require these tools.
"""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    blender = shutil.which("blender")
    if blender is None:
        raise SystemExit("Blender 4.3 or later is required to rebuild the exterior model.")
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_weapon_textures.py")], check=True)
    subprocess.run([blender, "--background", "--factory-startup", "--python",
                    str(ROOT / "tools" / "build_m1911_blender.py")], check=True, cwd=ROOT)
    scene = '''[gd_scene load_steps=5 format=3]

[ext_resource type="PackedScene" path="res://assets/models/m1911_slide.glb" id="1_slide"]
[ext_resource type="PackedScene" path="res://assets/models/m1911_frame.glb" id="2_frame"]
[ext_resource type="PackedScene" path="res://assets/models/m1911_grip.glb" id="3_grip"]
[ext_resource type="PackedScene" path="res://assets/models/m1911_magazine.glb" id="4_magazine"]

[node name="M1911Visual" type="Node3D"]

[node name="Slide" parent="." instance=ExtResource("1_slide")]

[node name="Frame" parent="." instance=ExtResource("2_frame")]

[node name="Grip" parent="." instance=ExtResource("3_grip")]
position = Vector3(0, -0.029, -0.009)
rotation = Vector3(-0.296706, 0, 0)

[node name="Magazine" parent="." instance=ExtResource("4_magazine")]
position = Vector3(0, -0.123, 0.019)
rotation = Vector3(-0.296706, 0, 0)

[node name="Muzzle" type="Marker3D" parent="."]
position = Vector3(0, 0.004, -0.196)
'''
    (ROOT / "scenes" / "m1911_visual.tscn").write_text(scene, encoding="utf-8")
    print("Generated four bevelled exterior GLBs and the stable animation wrapper.")


if __name__ == "__main__":
    main()
