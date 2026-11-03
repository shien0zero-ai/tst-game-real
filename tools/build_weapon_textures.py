#!/usr/bin/env python3
"""Generate original, deterministic sRGB/color and OpenGL-normal pistol PBR maps.

Requires NumPy and Pillow. No reference images or downloaded samples are used.
Walnut UVs use U across the panel and V along the grip; V=0 is the lower end.
"""
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "textures"
RNG = np.random.default_rng(1911)


def smoothstep(low, high, value):
    t = np.clip((value - low) / (high - low), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def noise(width, height, cells_x, cells_y):
    values = RNG.uniform(0.0, 1.0, (cells_y, cells_x))
    image = Image.fromarray(np.uint8(values * 255), "L")
    resized = image.resize((width, height), Image.Resampling.BICUBIC)
    result = np.asarray(resized, dtype=np.float32) / 255.0
    return (result - 0.5) * 2.0


def save_color(name, values):
    Image.fromarray(np.uint8(np.clip(values, 0, 255)), "RGB").save(OUTPUT / name)


def save_scalar(name, values):
    # RGB replication makes channels unambiguous for glTF's roughness packing.
    rgb = np.repeat(np.clip(values[..., None], 0.0, 1.0), 3, axis=2)
    save_color(name, rgb * 255)


def save_normal(name, height_map, physical_width, physical_height):
    rows, columns = height_map.shape
    dy, dx = np.gradient(height_map, physical_height / rows, physical_width / columns)
    # Image row direction is opposite UV V; these are OpenGL (positive Y) maps.
    vectors = np.stack((-dx, dy, np.ones_like(height_map)), axis=2)
    vectors /= np.linalg.norm(vectors, axis=2, keepdims=True)
    save_color(name, (vectors * 0.5 + 0.5) * 255)


def steel():
    width = height = 512
    grain = RNG.normal(0.0, 0.75, (height, width)).astype(np.float32)
    soft = noise(width, height, 32, 32)
    brushed = noise(width, height, 5, 256)
    hairline = np.zeros((height, width), dtype=np.float32)
    for _ in range(65):
        row = int(RNG.integers(0, height))
        start = int(RNG.integers(0, width - 45))
        length = int(RNG.integers(25, 180))
        end = min(width, start + length)
        hairline[row, start:end] += np.sin(np.linspace(0, np.pi, end - start))
    # Machined steel should read as one continuous finish at normal play distance.
    # Keep texture at a very fine scale instead of visible stone-like mottling.
    tone = 1.0 + grain * 0.003 + soft * 0.002 + brushed * 0.0012 + hairline * 0.008
    color = np.array([140.0, 148.0, 155.0])[None, None, :] * tone[..., None]
    rough = np.clip(0.35 + soft * 0.004 + grain * 0.003 - hairline * 0.018, 0.31, 0.38)
    micro_height = grain * 0.00000018 + brushed * 0.00000005 - hairline * 0.0000005
    save_color("weapon_steel_albedo.png", color)
    save_scalar("weapon_steel_roughness.png", rough)
    save_normal("weapon_steel_normal.png", micro_height, 0.04, 0.04)


def walnut():
    width, height = 512, 1024
    x = (np.arange(width, dtype=np.float32) + 0.5) / width
    y = 1.0 - (np.arange(height, dtype=np.float32) + 0.5) / height
    u, v = np.meshgrid(x, y)
    soft = noise(width, height, 7, 13)
    fine = RNG.normal(0.0, 0.65, (height, width)).astype(np.float32)
    flowing_u = u + np.sin(v * 8.0 * np.pi) * 0.006 + np.sin(v * 2.0 * np.pi) * 0.011
    broad = np.sin(2.0 * np.pi * (flowing_u * 9.0 + np.sin(v * 4.0) * 0.10))
    rings = np.sin(2.0 * np.pi * (flowing_u * 66.0 + soft * 0.13))
    pores = np.power(np.clip(0.5 + 0.5 * np.sin(2 * np.pi * (flowing_u * 125.0 + soft * 0.3)), 0, 1), 14)

    # Fine crossed cuts form little raised diamonds instead of painted lines.
    a, b = u * 22.0 + v * 54.0, u * 22.0 - v * 54.0
    triangle_a = 1.0 - np.abs((a % 1.0) * 2.0 - 1.0)
    triangle_b = 1.0 - np.abs((b % 1.0) * 2.0 - 1.0)
    raised_diamonds = np.minimum(triangle_a, triangle_b)
    check_mask = np.ones((height, width), dtype=np.float32)
    for center in (0.18, 0.83):
        distance = np.abs((u - 0.5) / 0.43) + np.abs((v - center) / 0.135)
        check_mask *= smoothstep(0.90, 1.05, distance)
    check_mask *= smoothstep(0.055, 0.11, u) * smoothstep(0.055, 0.11, 1.0 - u)
    check_mask *= smoothstep(0.025, 0.065, v) * smoothstep(0.025, 0.065, 1.0 - v)
    check_lighting = (raised_diamonds - 0.34) * 0.11 * check_mask
    tone = 1.0 + broad * 0.065 + rings * 0.021 + soft * 0.035 + fine * 0.008 - pores * 0.04 + check_lighting
    warm_color = np.array([101.0, 51.0, 28.0])[None, None, :]
    color = warm_color * tone[..., None]
    # Small warm growth bands keep the panel from reading as a flat brown fill.
    color[..., 0] += broad * 1.6
    color[..., 1] += broad * 0.4
    rough = np.clip(0.525 + soft * 0.025 + pores * 0.035 + check_mask * 0.07 + fine * 0.008, 0.46, 0.68)
    micro_height = raised_diamonds * check_mask * 0.000052 + rings * 0.0000016 - pores * 0.000004
    save_color("weapon_walnut_albedo.png", color)
    save_scalar("weapon_walnut_roughness.png", rough)
    save_normal("weapon_walnut_normal.png", micro_height, 0.036, 0.096)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    steel()
    walnut()
    print("Generated six original pistol PBR maps in", OUTPUT)
