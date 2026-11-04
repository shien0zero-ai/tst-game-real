#!/usr/bin/env python3
"""Create original, deterministic close-view pistol PBR textures.

Albedos are sRGB; roughness and OpenGL (+Y) tangent normals are linear data.
Metal maps describe a 180 x 40 mm patch: U follows the machining direction.
Walnut describes a 28 x 86 mm grip: U across, V from its bottom to its top.
The grip's double-diamond checkering is modeled, not painted into these maps.
Requires NumPy and Pillow. No sampled photographs or downloaded assets are used.
"""
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "textures"


def smoothstep(value):
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def noise(rng, width, height, cells_x, cells_y):
    """Periodic smooth value noise, including wraparound derivative continuity."""
    values = rng.uniform(-1.0, 1.0, (cells_y, cells_x)).astype(np.float32)
    x = np.arange(width, dtype=np.float32) * cells_x / width
    y = np.arange(height, dtype=np.float32) * cells_y / height
    ix, iy = x.astype(np.int32), y.astype(np.int32)
    sx = smoothstep(x - ix.astype(np.float32))
    sy = smoothstep(y - iy.astype(np.float32))
    left = values[iy[:, None], ix[None, :]]
    right = values[iy[:, None], ((ix + 1) % cells_x)[None, :]]
    top = left + (right - left) * sx[None, :]
    left = values[((iy + 1) % cells_y)[:, None], ix[None, :]]
    right = values[((iy + 1) % cells_y)[:, None], ((ix + 1) % cells_x)[None, :]]
    bottom = left + (right - left) * sx[None, :]
    return top + (bottom - top) * sy[:, None]


def save_color(name, values):
    encoded = np.rint(np.clip(values, 0, 255)).astype(np.uint8)
    save_png(name, encoded)


def save_png(name, encoded):
    # Rebuilds may run while the editor is open: never expose a partial PNG.
    target = OUTPUT / name
    temporary = target.with_suffix(".png.tmp")
    Image.fromarray(encoded, "RGB").save(temporary, format="PNG", compress_level=6)
    temporary.replace(target)


def save_scalar(name, values):
    # glTF packs roughness into G. RGB replication also works as a direct map.
    encoded = np.rint(np.clip(values, 0.0, 1.0) * 255).astype(np.uint8)
    rgb = np.repeat(encoded[..., None], 3, axis=2)
    save_png(name, rgb)


def save_normal(name, height_map, physical_width, physical_height, periodic=True):
    """Convert meter-valued surface relief to an unscaled OpenGL normal map."""
    rows, columns = height_map.shape
    if periodic:
        dx = (np.roll(height_map, -1, 1) - np.roll(height_map, 1, 1)) / (2 * physical_width / columns)
        dy = (np.roll(height_map, -1, 0) - np.roll(height_map, 1, 0)) / (2 * physical_height / rows)
    else:
        dy, dx = np.gradient(height_map, physical_height / rows, physical_width / columns)
    # Image rows run down, opposite to increasing UV V.
    vectors = np.stack((-dx, dy, np.ones_like(height_map)), axis=2)
    vectors /= np.linalg.norm(vectors, axis=2, keepdims=True)
    save_color(name, (vectors * 0.5 + 0.5) * 255)


def hairlines(rng, width, height, count):
    """A few shallow machining hairlines; no painted chips or broad grunge."""
    marks = np.zeros((height, width), dtype=np.float32)
    for _ in range(count):
        row = int(rng.integers(1, height - 1))
        start = int(rng.integers(0, width))
        length = int(rng.integers(22, 180))
        profile = np.sin(np.linspace(0, np.pi, length)).astype(np.float32)
        columns = (np.arange(length) + start) % width
        amplitude = float(rng.uniform(0.25, 0.75))
        marks[row, columns] = np.maximum(marks[row, columns], profile * amplitude)
        marks[row + 1, columns] = np.maximum(marks[row + 1, columns], profile * amplitude * 0.18)
    return marks


def steel():
    """Dark, nearly neutral blued steel with a fine longitudinal satin finish."""
    rng = np.random.default_rng(1911)
    width = height = 2048
    fine = rng.normal(0.0, 1.0, (height, width)).astype(np.float32)
    finish = noise(rng, width, height, 110, 1400)
    long_finish = noise(rng, width, height, 16, 580)
    oxidation = noise(rng, width, height, 8, 9)
    marks = hairlines(rng, width, height, 95)

    # Bluing changes the reflectance; the surface should never read as chrome.
    # Nearly neutral color avoids a second blue tint on top of sky reflections.
    tone = oxidation * 1.25 + finish * 1.15 + fine * 0.42 + marks * 2.6
    color = np.array([79.0, 81.0, 80.0], dtype=np.float32)[None, None, :] + tone[..., None]
    rough = np.clip(0.415 + long_finish * 0.026 + finish * 0.019
                    + oxidation * 0.009 + fine * 0.005 - marks * 0.047, 0.335, 0.48)
    surface = finish * 0.0000015 + long_finish * 0.0000008 + fine * 0.00000024 - marks * 0.0000014
    save_color("weapon_steel_albedo.png", color)
    save_scalar("weapon_steel_roughness.png", rough)
    save_normal("weapon_steel_normal.png", surface, 0.180, 0.040)


def brushed():
    """Unblued barrel/chamber steel: warm neutral iron, restrained machining."""
    rng = np.random.default_rng(1912)
    width = height = 2048
    fine = rng.normal(0.0, 1.0, (height, width)).astype(np.float32)
    finish = noise(rng, width, height, 95, 1550)
    long_finish = noise(rng, width, height, 12, 710)
    broad = noise(rng, width, height, 7, 6)
    marks = hairlines(rng, width, height, 125)
    tone = finish * 1.9 + long_finish * 1.1 + fine * 0.55 + broad * 0.65 + marks * 2.0
    color = np.array([174.0, 175.0, 169.0], dtype=np.float32)[None, None, :] + tone[..., None]
    rough = np.clip(0.262 + long_finish * 0.042 + finish * 0.025
                    + fine * 0.006 + broad * 0.009 - marks * 0.035, 0.18, 0.35)
    surface = finish * 0.0000018 + long_finish * 0.0000010 + fine * 0.00000025 - marks * 0.0000015
    save_color("weapon_brushed_albedo.png", color)
    save_scalar("weapon_brushed_roughness.png", rough)
    save_normal("weapon_brushed_normal.png", surface, 0.180, 0.040)


def walnut_pores(rng, width, height):
    """Small, elongated open grain pores with tapered ends and varied depth."""
    pores = np.zeros((height, width), dtype=np.float32)
    for _ in range(4200):
        center_x = float(rng.uniform(0, width))
        center_y = float(rng.uniform(0, height))
        radius_x = float(rng.uniform(0.38, 1.15))
        radius_y = float(rng.uniform(1.8, 12.0))
        if rng.random() < 0.08:
            radius_y *= 1.8
        x0 = max(0, int(center_x - radius_x * 2.5))
        x1 = min(width, int(center_x + radius_x * 2.5) + 1)
        y0 = max(0, int(center_y - radius_y * 2.0))
        y1 = min(height, int(center_y + radius_y * 2.0) + 1)
        x = (np.arange(x0, x1, dtype=np.float32) - center_x) / radius_x
        y = (np.arange(y0, y1, dtype=np.float32) - center_y) / radius_y
        pore = np.exp(-(x[None, :] ** 2 + y[:, None] ** 2) * 1.6)
        pore *= float(rng.uniform(0.18, 0.85))
        pores[y0:y1, x0:x1] = np.maximum(pores[y0:y1, x0:x1], pore)
    return pores


def growth_ribbon(rng, coordinates, count):
    """Irregular-width lengthwise grain, bent continuously by the sawn figure."""
    lattice = rng.uniform(-1.0, 1.0, count).astype(np.float32)
    position = (coordinates % 1.0) * count
    index = position.astype(np.int32)
    weight = smoothstep(position - index.astype(np.float32))
    return lattice[index] * (1.0 - weight) + lattice[(index + 1) % count] * weight


def walnut():
    """Dark oil-finished walnut with quiet, irregular lengthwise growth grain."""
    rng = np.random.default_rng(1913)
    width, height = 1024, 2048
    x = (np.arange(width, dtype=np.float32) + 0.5) / width
    y = 1.0 - (np.arange(height, dtype=np.float32) + 0.5) / height
    u, v = np.meshgrid(x, y)
    flow = noise(rng, width, height, 5, 7)
    fine = rng.normal(0.0, 1.0, (height, width)).astype(np.float32)
    long_grain = noise(rng, width, height, 75, 6)
    broad = noise(rng, width, height, 11, 3)

    # Nonuniform growth widths and gentle continuous wandering avoid evenly
    # repeated stripes or the large orange rings of stained construction pine.
    flowing_u = u + flow * 0.022 + np.sin(v * 5.1 + 0.6) * 0.014
    flowing_u += np.sin(v * 2.3 + u * 8.0) * 0.006
    growth = growth_ribbon(rng, flowing_u, 23) * 0.68
    growth += growth_ribbon(rng, flowing_u, 67) * 0.24
    growth += growth_ribbon(rng, flowing_u, 157) * 0.12
    dark_fibers = np.maximum(growth_ribbon(rng, flowing_u, 273), 0) ** 8
    pores = walnut_pores(rng, width, height)

    tone = growth * 7.2 + broad * 6.4 + long_grain * 3.2 + fine * 0.55 - dark_fibers * 1.8
    # A restrained walnut palette. Small chroma variation follows growth rather
    # than random RGB noise; cavities are dark but carry no baked illumination.
    color = np.array([75.0, 51.0, 35.0], dtype=np.float32)[None, None, :]
    color = color + tone[..., None] * np.array([1.0, 0.81, 0.65], dtype=np.float32)
    color *= 1.0 - pores[..., None] * 0.19
    rough = np.clip(0.446 + broad * 0.022 + long_grain * 0.017
                    + dark_fibers * 0.015 + pores * 0.070 + fine * 0.004, 0.38, 0.55)
    # Relief is microscopic wood fiber and open pore depth only. Raised grip
    # diamonds, clean borders and the two screw diamonds are real geometry.
    surface = growth * 0.00000045 + long_grain * 0.00000050
    surface -= dark_fibers * 0.0000010 + pores * 0.0000055
    surface += fine * 0.00000008
    save_color("weapon_walnut_albedo.png", color)
    save_scalar("weapon_walnut_roughness.png", rough)
    save_normal("weapon_walnut_normal.png", surface, 0.028, 0.086, periodic=False)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    steel()
    brushed()
    walnut()
    print("Generated nine original close-view pistol PBR maps in", OUTPUT)
