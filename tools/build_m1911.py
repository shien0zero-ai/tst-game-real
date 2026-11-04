#!/usr/bin/env python3
"""Adapt the contained CC BY M1911 prop and write its stable Godot wrapper.

Requires Blender 4.3+ on the asset-authoring machine only. Source art and
attribution are in tools/source_assets/m1911/. No network or account is needed.
The shipped game uses the exported GLBs and does not require authoring tools.
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
    subprocess.run([blender, "--background", "--factory-startup", "--python",
                    str(ROOT / "tools" / "adapt_m1911_blender.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "tools" / "share_m1911_textures.py")],
                   check=True, cwd=ROOT)
    scene = '''[gd_scene load_steps=4 format=3]

[ext_resource type="PackedScene" path="res://assets/models/m1911_slide.glb" id="1_slide"]
[ext_resource type="PackedScene" path="res://assets/models/m1911_frame.glb" id="2_frame"]
[ext_resource type="PackedScene" path="res://assets/models/m1911_magazine.glb" id="3_magazine"]

[node name="M1911Visual" type="Node3D"]

[node name="Slide" parent="." instance=ExtResource("1_slide")]

[node name="Frame" parent="." instance=ExtResource("2_frame")]

[node name="Grip" type="Node3D" parent="."]

[node name="Magazine" parent="." instance=ExtResource("3_magazine")]

[node name="Muzzle" type="Marker3D" parent="."]
position = Vector3(0, 0.004, -0.196)
'''
    (ROOT / "scenes" / "m1911_visual.tscn").write_text(scene, encoding="utf-8")
    print("Adapted the licensed M1911 prop and retained the animation node paths.")


if __name__ == "__main__":
    main()
