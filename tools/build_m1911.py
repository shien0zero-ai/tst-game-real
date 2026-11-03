#!/usr/bin/env python3
"""Generate an editable, unbranded M1911-inspired visual for the game.

This is an original exterior-only prop made from Godot primitive meshes.
Run with Python 3 from any directory; no Blender or downloaded assets required.
"""
from pathlib import Path
from math import atan2, hypot, pi

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = {
    'steel': ('Parkerized slide', (0.27, 0.29, 0.31), 0.86, 0.34),
    'frame': ('Dark steel frame', (0.19, 0.21, 0.22), 0.78, 0.44),
    'barrel': ('Satin steel accents', (0.49, 0.52, 0.54), 0.94, 0.23),
    'black': ('Recesses and sight black', (0.014, 0.017, 0.019), 0.25, 0.64),
    'checkering': ('Walnut checkering', (0.105, 0.043, 0.019), 0.0, 0.82),
    'white': ('Sight dots', (0.91, 0.92, 0.82), 0.05, 0.45),
}
for key, (name, color, metallic, roughness) in MATERIALS.items():
    (ROOT / 'materials' / f'weapon_{key}.tres').write_text(
        '[gd_resource type="StandardMaterial3D" format=3]\n\n[resource]\n'
        f'resource_name = "{name}"\n'
        f'albedo_color = Color({color[0]}, {color[1]}, {color[2]}, 1)\n'
        f'metallic = {metallic}\nroughness = {roughness}\n', encoding='utf-8')
(ROOT / 'materials' / 'weapon_walnut.tres').write_text('''[gd_resource type="StandardMaterial3D" load_steps=4 format=3]

[sub_resource type="FastNoiseLite" id="Noise_wood"]
seed = 1911
noise_type = 3
frequency = 0.04
fractal_octaves = 3

[sub_resource type="Gradient" id="Gradient_wood"]
colors = PackedColorArray(0.075, 0.024, 0.01, 1, 0.34, 0.145, 0.055, 1)

[sub_resource type="NoiseTexture2D" id="Texture_wood"]
width = 256
height = 256
seamless = true
color_ramp = SubResource("Gradient_wood")
noise = SubResource("Noise_wood")

[resource]
resource_name = "Oiled walnut grip"
albedo_texture = SubResource("Texture_wood")
roughness = 0.57
uv1_scale = Vector3(0.4, 5, 1)
''', encoding='utf-8')

resources = []
nodes = []
mesh_cache = {}

def vec(v):
    return 'Vector3(' + ', '.join(f'{n:.7g}' for n in v) + ')'

def node(name, parent='.', pos=None, rot=None, kind='Node3D', props=()):
    s = f'[node name="{name}" type="{kind}" parent="{parent}"]\n'
    if pos: s += f'position = {vec(pos)}\n'
    if rot: s += f'rotation = {vec(rot)}\n'
    s += ''.join(p + '\n' for p in props)
    nodes.append(s)

def mesh(kind, mat, **props):
    key = (kind, mat, tuple(sorted(props.items())))
    if key in mesh_cache: return mesh_cache[key]
    rid = f'Mesh_{len(resources) + 1}'
    s = f'[sub_resource type="{kind}" id="{rid}"]\nmaterial = ExtResource("{mat}")\n'
    for k, v in props.items():
        s += f'{k} = {vec(v) if isinstance(v, tuple) else v}\n'
    resources.append(s)
    mesh_cache[key] = rid
    return rid

def part(name, parent, mat, size, pos, rot=None, **kwargs):
    rid = mesh('BoxMesh', mat, size=size)
    node(name, parent, pos, rot, 'MeshInstance3D', [f'mesh = SubResource("{rid}")', 'cast_shadow = 0'])

def cylinder(name, parent, mat, radius, height, pos, rot=(pi / 2, 0, 0), top=None):
    rid = mesh('CylinderMesh', mat, top_radius=radius if top is None else top,
               bottom_radius=radius, height=height, radial_segments=32, rings=1)
    node(name, parent, pos, rot, 'MeshInstance3D', [f'mesh = SubResource("{rid}")', 'cast_shadow = 0'])

node('Slide')
part('SlideFlats', 'Slide', 'steel', (.033, .026, .184), (0, -.001, -.09))
cylinder('RoundedTop', 'Slide', 'steel', .0165, .18, (0, .009, -.09))
part('TopFlat', 'Slide', 'steel', (.013, .003, .177), (0, .024, -.09))
part('LowerRail', 'Slide', 'black', (.034, .002, .182), (0, -.0145, -.09))
part('RearPlate', 'Slide', 'steel', (.032, .027, .004), (0, .001, .003))
# Exterior surface details avoid geometry dependencies and remain individually editable.
part('EjectionPortRecess', 'Slide', 'black', (.0007, .014, .03), (.0168, .004, -.064))
part('EjectionPortBarrel', 'Slide', 'barrel', (.0008, .008, .024), (.0173, .003, -.063))
part('EjectionPortTop', 'Slide', 'black', (.014, .0008, .026), (.0075, .0239, -.064))
for side, x in [('Right', .017), ('Left', -.017)]:
    for i in range(9):
        part(f'{side}Serration{i + 1:02}', 'Slide', 'black', (.0007, .021, .0012),
             (x, -.0005, -.004 - i * .0035), (.12, 0, 0))
part('RearSightBase', 'Slide', 'black', (.025, .0035, .009), (0, .0275, -.004))
for label, x in [('Left', -.0085), ('Right', .0085)]:
    part(f'RearSight{label}', 'Slide', 'black', (.0065, .008, .008), (x, .033, -.004))
    cylinder(f'RearDot{label}', 'Slide', 'white', .0012, .0007, (x, .033, .0003))
part('FrontSight', 'Slide', 'black', (.004, .006, .013), (0, .028, -.169))
cylinder('FrontSightDot', 'Slide', 'white', .0011, .0006, (0, .028, -.1621))
# The barrel is stationary when the slide moves; only the visible prop exterior is modeled.
node('Frame')
part('FrameRail', 'Frame', 'frame', (.032, .014, .154), (0, -.023, -.073))
part('DustCover', 'Frame', 'frame', (.026, .015, .077), (0, -.032, -.118))
cylinder('BarrelSleeve', 'Frame', 'steel', .012, .007, (0, .004, -.184))
cylinder('BarrelMuzzle', 'Frame', 'barrel', .0091, .009, (0, .004, -.191))
cylinder('MuzzleBore', 'Frame', 'black', .0062, .0005, (0, .004, -.1958))
cylinder('RecoilPlug', 'Frame', 'steel', .0055, .004, (0, -.014, -.181))
# An open guard assembled from slim exterior sections and rounded corners.
part('GuardFront', 'Frame', 'frame', (.011, .033, .006), (0, -.052, -.091), (-.13, 0, 0))
part('GuardBottom', 'Frame', 'frame', (.011, .006, .047), (0, -.071, -.065))
part('GuardRear', 'Frame', 'frame', (.011, .022, .006), (0, -.062, -.039), (.3, 0, 0))
cylinder('GuardFrontCorner', 'Frame', 'frame', .0041, .011, (0, -.068, -.087), (0, 0, pi / 2))
part('Trigger', 'Frame', 'barrel', (.012, .021, .0045), (0, -.044, -.058), (-.15, 0, 0))
for i in range(3):
    cylinder(f'TriggerDetail{i + 1}', 'Frame', 'black', .0013, .0005,
             (.0062, -.0385 - i * .0055, -.057), (0, 0, pi / 2))
# Walnut grip and long backstrap silhouette.
node('Grip', pos=(0, -.029, -.009), rot=(-.296706, 0, 0))
part('GripFrame', 'Grip', 'frame', (.034, .096, .037), (0, -.046, 0))
part('Backstrap', 'Grip', 'steel', (.028, .091, .004), (0, -.045, .0195))
for label, side in [('Right', 1), ('Left', -1)]:
    part(f'{label}PanelEdge', 'Grip', 'checkering', (.004, .085, .035), (side * .0185, -.047, .0007))
    part(f'{label}WalnutPanel', 'Grip', 'walnut', (.003, .081, .032), (side * .0202, -.047, .0007))
    # Diagonal crosshatching clipped to the rectangular panel creates a fine grip texture.
    for slope in (-1.3, 1.3):
        for i in range(-10, 11):
            intercept = i * .0042
            zlo, zhi = -.0125, .0125
            a, b = (-.034 - intercept) / slope, (.034 - intercept) / slope
            zlo = max(zlo, min(a, b))
            zhi = min(zhi, max(a, b))
            if zhi - zlo <= .001: continue
            ya, yb = slope * zlo + intercept, slope * zhi + intercept
            angle = atan2(zhi - zlo, yb - ya)
            part(f'{label}Check{int(slope > 0)}_{i + 10:02}', 'Grip', 'checkering',
                 (.0004, hypot(yb - ya, zhi - zlo), .00045),
                 (side * .0219, -.047 + (ya + yb) / 2, .0007 + (zlo + zhi) / 2), (angle, 0, 0))
    for i, y in enumerate((-.016, -.079)):
        cylinder(f'{label}Screw{i + 1}', 'Grip', 'barrel', .0025, .0008,
                 (side * .0222, y, .0007), (0, 0, pi / 2))
        part(f'{label}ScrewSlot{i + 1}', 'Grip', 'black', (.0003, .0006, .003),
             (side * .0228, y, .0007))
# Small recognizable exterior controls.
part('HammerSpur', 'Frame', 'steel', (.01, .007, .019), (0, .012, .015), (-.35, 0, 0))
part('HammerInset', 'Frame', 'black', (.005, .001, .012), (0, .016, .016), (-.35, 0, 0))
part('Beavertail', 'Frame', 'frame', (.023, .006, .024), (0, -.025, .015), (-.25, 0, 0))
part('ThumbSafety', 'Frame', 'steel', (.005, .004, .017), (-.0185, -.023, -.01))
part('SlideStop', 'Frame', 'steel', (.003, .0035, .024), (-.0179, -.023, -.057))
cylinder('SlideStopPin', 'Frame', 'steel', .0031, .003, (-.018, -.024, -.041), (0, 0, pi / 2))
cylinder('MagazineCatch', 'Frame', 'steel', .0036, .003, (-.0188, -.036, -.026), (0, 0, pi / 2))
node('Magazine', pos=(0, -.123, .019), rot=(-.296706, 0, 0))
part('Baseplate', 'Magazine', 'steel', (.036, .006, .04), (0, 0, 0))
node('Muzzle', pos=(0, .004, -.196), kind='Marker3D')

material_names = list(MATERIALS) + ['walnut']
text = f'[gd_scene load_steps={1 + len(material_names) + len(resources)} format=3]\n\n'
for name in material_names:
    text += f'[ext_resource type="Material" path="res://materials/weapon_{name}.tres" id="{name}"]\n'
text += '\n' + '\n'.join(resources)
text += '\n[node name="M1911Visual" type="Node3D"]\n\n'
text += '\n'.join(nodes)
(ROOT / 'scenes' / 'm1911_visual.tscn').write_text(text, encoding='utf-8')
print(f'Generated {len(nodes)} nodes, {len(resources)} meshes and {len(material_names)} materials.')
