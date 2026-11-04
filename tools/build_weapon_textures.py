#!/usr/bin/env python3
"""Create original, deterministic close-view pistol PBR textures.

Albedos are sRGB; roughness and OpenGL (+Y) tangent normals are linear data.
Metal maps describe a 180 x 40 mm patch: U follows the machining direction.
Walnut describes a 33 x 110 mm grip: U across, V from its bottom to its top.
The grip's double-diamond checkering is modeled, not painted into these maps.
Slide and frame use nonrepeating, face-specific atlases shared with the model
generator. Their wear follows physical handling areas; stamped lettering is
recessed in their normal maps rather than floating above the gun as a label.
Requires NumPy and Pillow. No sampled photographs or downloaded assets are used.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


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


def normal_values(height_map, physical_width, physical_height, periodic=True):
    """Convert meter-valued relief to an unscaled OpenGL normal map."""
    rows, columns = height_map.shape
    if periodic:
        dx = (np.roll(height_map, -1, 1) - np.roll(height_map, 1, 1)) / (2 * physical_width / columns)
        dy = (np.roll(height_map, -1, 0) - np.roll(height_map, 1, 0)) / (2 * physical_height / rows)
    else:
        dy, dx = np.gradient(height_map, physical_height / rows, physical_width / columns)
    # Image rows run down, opposite to increasing UV V.
    vectors = np.stack((-dx, dy, np.ones_like(height_map)), axis=2)
    vectors /= np.linalg.norm(vectors, axis=2, keepdims=True)
    return np.rint((vectors * 0.5 + 0.5) * 255).astype(np.uint8)


def save_normal(name, height_map, physical_width, physical_height, periodic=True):
    save_png(name, normal_values(height_map, physical_width, physical_height, periodic))


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


def oval(u, v, center_u, center_v, width, height):
    return np.exp(-(((u-center_u)/width)**2 + ((v-center_v)/height)**2) * 2.0)


def fine_damage(rng, width, height, physical_width, physical_height, density=1.0):
    """Isolated shallow pits and tapered scuffs at measured submillimeter scale."""
    pits = Image.new("L", (width, height))
    scratches = Image.new("L", (width, height))
    pit_draw, scratch_draw = ImageDraw.Draw(pits), ImageDraw.Draw(scratches)
    ppm_x, ppm_y = width / (physical_width*1000), height / (physical_height*1000)
    count = int(physical_width * physical_height * 1_100_000 * density)
    for _ in range(count):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        radius = float(rng.uniform(.012, .055))
        if rng.random() < .035:
            radius *= 2.1
        rx, ry = max(.42, radius*ppm_x), max(.42, radius*ppm_y)
        depth = int(rng.uniform(35, 190))
        pit_draw.ellipse((x-rx, y-ry, x+rx, y+ry), fill=depth)
    for _ in range(max(15, int(count*.018))):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        length = float(rng.uniform(.30, 2.7)) * ppm_x
        slope = float(rng.uniform(-.22, .22)) * ppm_y / ppm_x
        scratch_draw.line((x,y,x+length,y+length*slope), fill=int(rng.uniform(65,185)), width=1)
    p = np.asarray(pits.filter(ImageFilter.GaussianBlur(.34)), dtype=np.float32)/255
    s = np.asarray(scratches.filter(ImageFilter.GaussianBlur(.27)), dtype=np.float32)/255
    return p, s


def aged_metal(rng, width, height, physical_width, physical_height, region):
    """Worn bluing, coherent grease marks and hand/holster contact, without rust."""
    x = (np.arange(width, dtype=np.float32)+.5)/width
    y = 1-(np.arange(height, dtype=np.float32)+.5)/height
    u, v = np.meshgrid(x,y)
    cloud = noise(rng,width,height,7,5)
    mid = noise(rng,width,height,29,17)
    fine_cloud = noise(rng,width,height,140,85)
    machining = noise(rng,width,height,65,max(160,height//2))
    speckle = rng.normal(0,1,(height,width)).astype(np.float32)
    # The large fields affect the remaining oxide, not diffuse illumination.
    worn = .61 + cloud*.19 + mid*.105 + fine_cloud*.043
    if region in ("left", "right"):
        front = oval(u,v,.025,.53,.15,.82)
        shoulder = oval(u,v,.47,.91,.67,.15)
        thumb = oval(u,v,.84,.40,.14,.44)
        edge = np.exp(-v/.016)*.33 + np.exp(-u/.024)*.35
        contact = front*.75 + shoulder*.45 + thumb*.20 + edge
        # Cocking-serration valleys retain the darker finish; the geometry
        # supplies exposed raised ridges rather than a painted checker pattern.
        serrations = smoothstep((u-.84)/.045) * (1-smoothstep((v-.57)/.10))
        worn += contact*.28 - serrations*.17
        grease = oval(u,v,.70,.24,.21,.14) + oval(u,v,.86,.48,.11,.28)*.65
    elif region == "frame":
        contact = oval(u,v,.12,.67,.35,.60)*.45 + oval(u,v,.68,.33,.20,.54)*.50
        worn += contact*.30
        grease = oval(u,v,.63,.47,.15,.28)*.9 + oval(u,v,.79,.22,.10,.29)
    elif region == "top":
        contact = oval(u,v,.06,.5,.18,.9)*.65 + (np.exp(-v/.065)+np.exp(-(1-v)/.065))*.32
        worn += contact*.30
        grease = oval(u,v,.73,.5,.18,.42)*.7
    elif region == "front":
        contact = np.maximum(np.exp(-u/.12),np.exp(-(1-u)/.12))
        worn += .09 + contact*.13
        grease = oval(u,v,.5,.32,.30,.19)*.5
    elif region == "rear":
        worn -= .06
        contact = oval(u,v,.5,.7,.45,.24)*.5
        grease = oval(u,v,.50,.35,.35,.32)
    elif region == "under":
        worn -= .12
        contact = np.exp(-v/.07)+np.exp(-(1-v)/.07)
        worn += contact*.14
        grease = oval(u,v,.75,.5,.22,.42)*.7
    else:
        contact = oval(u,v,.33,.58,.44,.35)*.6
        worn += contact*.17
        grease = oval(u,v,.65,.45,.28,.27)*.7
    worn = np.clip(worn, .16, .98)
    pits, scratches = fine_damage(rng,width,height,physical_width,physical_height)
    retained = 1-worn
    oxide = np.array([62.,67.,68.],dtype=np.float32)
    exposed = np.array([153.,155.,151.],dtype=np.float32)
    color = oxide[None,None,:] * retained[...,None] + exposed[None,None,:]*worn[...,None]
    variation = machining*.50 + fine_cloud*1.35 + speckle*.24
    color += variation[...,None]
    color -= pits[...,None]*(7.5+retained[...,None]*6.0)
    color += scratches[...,None]*(9+contact[...,None]*8)
    # Faint gray-green/brown oxide in sheltered frame regions; no orange rust.
    if region == "frame":
        sheltered = (oval(u,v,.60,.23,.24,.32)+oval(u,v,.83,.55,.13,.37))*.65
        color += sheltered[...,None]*np.array([.4,1.4,-1.9],dtype=np.float32)
    rough = .476 - worn*.123 + cloud*.023 + mid*.027 + fine_cloud*.015
    rough -= grease*(.044+mid*.025)
    rough += pits*.10 - scratches*.075 + machining*.010
    rough = np.clip(rough,.255,.57)
    surface = machining*.00000039 + fine_cloud*.00000017
    surface -= pits*.000013 + scratches*.0000020
    return color,rough,surface


def steel():
    """Aged controls/frame metal, with more remaining bluing than the slide."""
    rng = np.random.default_rng(1911)
    width = height = 2048
    color,rough,surface = aged_metal(rng,width,height,.180,.040,"controls")
    color *= .90
    save_color("weapon_steel_albedo.png", color)
    save_scalar("weapon_steel_roughness.png", rough)
    save_normal("weapon_steel_normal.png", surface, 0.180, 0.040)


def font_path():
    candidates = (
        Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError("A system serif TrueType font is required for recessed markings")


def stamped_line(mask, text, center, size, opacity=255):
    """Rasterize a small metal roll mark; its mask becomes recessed height."""
    font = ImageFont.truetype(str(font_path()), 180)
    bounds = font.getbbox(text)
    glyphs = Image.new("L", (bounds[2]-bounds[0]+8,bounds[3]-bounds[1]+8))
    ImageDraw.Draw(glyphs).text((4-bounds[0],4-bounds[1]),text,font=font,fill=opacity)
    glyphs = glyphs.crop(glyphs.getbbox())
    glyphs = glyphs.resize((max(1,int(size[0])),max(1,int(size[1]))), Image.Resampling.LANCZOS)
    position = (int(center[0]-glyphs.width/2),int(center[1]-glyphs.height/2))
    mask.paste(glyphs,position,glyphs)


def slide_markings(width,height):
    mask = Image.new("L", (width,height))

    def line(text,z,y,physical_width,cap_height,opacity=225):
        center = ((z+.182)/.187*width,(1-(y+.014)/.02825)*height)
        size = (physical_width/.187*width,cap_height/.02825*height)
        stamped_line(mask,text,center,size,opacity)

    line("PATENTED APR.20.1897. SEPT.9.1902.",-.129,-.0031,.052,.00120)
    line("DEC.19.1905. FEB.14.1911. AUG.19.1913.",-.129,-.0051,.054,.00110)
    line("COLT'S PT. F.A. MFG. CO.",-.0655,-.0031,.038,.00120)
    line("HARTFORD. CT. U.S.A.",-.0655,-.0051,.034,.00110)

    # An intentionally faint, partly lost historic stamp impression. The
    # supplied photo resolves only a broken ring and rearing-horse strokes.
    diameter = max(24,int(.0042/.187*width))
    stamp = Image.new("L", (diameter*3,diameter*3))
    draw = ImageDraw.Draw(stamp)
    a = diameter*3
    inset = a*.10
    draw.arc((inset,inset,a-inset,a-inset),8,134,fill=125,width=2)
    draw.arc((inset,inset,a-inset,a-inset),153,243,fill=110,width=2)
    draw.arc((inset,inset,a-inset,a-inset),265,343,fill=135,width=2)
    stroke = max(2,int(a*.027))
    def path(points,fill=140):
        draw.line([(int(x*a),int(y*a)) for x,y in points],fill=fill,width=stroke,joint="curve")
    path(((.39,.61),(.49,.48),(.50,.34),(.58,.24),(.66,.25),(.61,.32),(.58,.41),(.62,.50),(.58,.63)))
    path(((.51,.43),(.40,.37),(.35,.43),(.43,.49)))
    path(((.58,.41),(.71,.39),(.73,.46)))
    path(((.57,.60),(.69,.71),(.72,.78)))
    path(((.49,.60),(.43,.71),(.51,.79)))
    path(((.40,.57),(.28,.52),(.25,.44),(.29,.39)),95)
    stamp = stamp.resize((diameter,diameter),Image.Resampling.LANCZOS)
    center = ((.0012+.182)/.187*width,(1-(-.004+.014)/.02825)*height)
    mask.paste(stamp,(int(center[0]-diameter/2),int(center[1]-diameter/2)),stamp)
    return np.asarray(mask,dtype=np.float32)/255


def frame_markings(width,height):
    mask = Image.new("L", (width,height))
    center = ((-.138+.169)/.201*width,(1-(-.0215+.052)/.038)*height)
    stamped_line(mask,"UNITED STATES PROPERTY",center,
                 (.035/.201*width,.00145/.038*height),210)
    return np.asarray(mask,dtype=np.float32)/255


def metal_atlas(name, definitions, seed):
    """Use the exact face UV rectangles in build_m1911_blender.py."""
    width,height = 4096,2048
    canvases = {
        "albedo":Image.new("RGB",(width,height),(112,116,115)),
        "roughness":Image.new("RGB",(width,height),(103,103,103)),
        "normal":Image.new("RGB",(width,height),(128,128,255)),
    }
    rng = np.random.default_rng(seed)
    for region,uv,physical_size,marking in definitions:
        u0,v0,u1,v1 = uv
        x0,x1 = int(round(u0*width)),int(round(u1*width))
        y0,y1 = int(round((1-v1)*height)),int(round((1-v0)*height))
        w,h = x1-x0,y1-y0
        color,rough,surface = aged_metal(rng,w,h,*physical_size,region)
        if marking:
            mask = marking(w,h)
            surface -= mask*.000045
            color -= mask[...,None]*20.0
            rough += mask*.035
        arrays = {
            "albedo":np.rint(np.clip(color,0,255)).astype(np.uint8),
            "roughness":np.repeat(np.rint(np.clip(rough,0,1)*255).astype(np.uint8)[...,None],3,axis=2),
            "normal":normal_values(surface,*physical_size,periodic=False),
        }
        for suffix,array in arrays.items():
            island = Image.fromarray(array,"RGB")
            canvas = canvases[suffix]
            # Two pixels of dilation prevent dark sampling at atlas boundaries.
            canvas.paste(island.resize((w+4,h+4),Image.Resampling.NEAREST),(x0-2,y0-2))
            canvas.paste(island,(x0,y0))
    for suffix,canvas in canvases.items():
        save_png(f"weapon_{name}_{suffix}.png",np.asarray(canvas))


def slide():
    metal_atlas("slide",(
        ("left",(.02,.02,.98,.30),(.187,.02825),slide_markings),
        ("right",(.02,.36,.98,.64),(.187,.02825),None),
        ("top",(.02,.70,.98,.82),(.187,.0256),None),
        ("front",(.02,.86,.16,.98),(.0256,.02825),None),
        ("rear",(.20,.86,.34,.98),(.0256,.02825),None),
        ("under",(.38,.86,.98,.98),(.187,.0256),None),
    ),1917)


def frame():
    metal_atlas("frame",(
        ("frame",(.02,.02,.98,.46),(.201,.038),frame_markings),
        ("frame",(.02,.52,.98,.96),(.201,.038),None),
        ("under",(.02,.47,.98,.51),(.201,.033),None),
    ),1918)


def brushed():
    """Unblued barrel/chamber steel: warm neutral iron, restrained machining."""
    rng = np.random.default_rng(1912)
    width = height = 2048
    fine = rng.normal(0.0, 1.0, (height, width)).astype(np.float32)
    finish = noise(rng, width, height, 95, 1550)
    long_finish = noise(rng, width, height, 12, 710)
    broad = noise(rng, width, height, 7, 6)
    marks = hairlines(rng, width, height, 125)
    tone = finish * 1.0 + long_finish * .7 + fine * .22 + broad * 2.1 + marks * 3.0
    color = np.array([163.0, 166.0, 165.0], dtype=np.float32)[None, None, :] + tone[..., None]
    rough = np.clip(0.305 + long_finish * 0.030 + finish * 0.015
                    + fine * 0.003 + broad * 0.028 - marks * 0.035, 0.22, 0.40)
    surface = finish * 0.00000060 + long_finish * 0.00000032 - marks * 0.0000015
    save_color("weapon_brushed_albedo.png", color)
    save_scalar("weapon_brushed_roughness.png", rough)
    save_normal("weapon_brushed_normal.png", surface, 0.180, 0.040)

    # Exposed high points are still gray aged iron, not mirror/chrome edges.
    # Reusing the exact normal pixels also lets runtime packaging deduplicate.
    exposed_color = color + np.array([5.,4.,4.],dtype=np.float32)[None,None,:]
    save_color("weapon_exposed_albedo.png", exposed_color)
    save_scalar("weapon_exposed_roughness.png", np.clip(rough-.018,.22,.40))
    save_normal("weapon_exposed_normal.png", surface, 0.180, 0.040)


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
    """Handled, very dark red-brown walnut; no orange stain or painted checks."""
    rng = np.random.default_rng(1913)
    width = height = 2048
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

    tone = growth*3.4 + broad*3.6 + long_grain*1.2 + fine*.20 - dark_fibers*.9
    # The two uncut diamonds and smoothly rubbed border are lighter than the
    # near-black checker field. These masks share the actual panel/screw UVs.
    diamonds = np.zeros((height,width),dtype=np.float32)
    for center in (.13182,.87455):
        distance = np.abs(u-.5)/.21818 + np.abs(v-center)/.09545
        diamonds = np.maximum(diamonds,1-smoothstep((distance-.90)/.20))
    border = 1-smoothstep((np.minimum(u,1-u)-.025)/.035)
    border = np.maximum(border,1-smoothstep((np.minimum(v,1-v)-.018)/.027))
    smooth_wood = np.maximum(diamonds,border*.80)
    base = np.array([30.,19.,19.],dtype=np.float32)[None,None,:]
    plain = np.array([50.,30.,27.],dtype=np.float32)[None,None,:]
    color = base*(1-smooth_wood[...,None]) + plain*smooth_wood[...,None]
    color += tone[...,None]*np.array([1.,.65,.58],dtype=np.float32)
    color *= 1-pores[...,None]*.15
    handled = oval(u,v,.69,.46,.37,.31)*.65 + oval(u,v,.29,.18,.30,.21)*.45
    rough = np.clip(.562-smooth_wood*.085-handled*.027 + broad*.021
                    + long_grain*.012 + dark_fibers*.01 + pores*.055, .405,.64)
    # Relief is microscopic wood fiber and open pore depth only. Raised grip
    # diamonds, clean borders and the two screw diamonds are real geometry.
    surface = growth*.00000030 + long_grain*.00000035
    surface -= dark_fibers*.0000008 + pores*.0000048
    save_color("weapon_walnut_albedo.png", color)
    save_scalar("weapon_walnut_roughness.png", rough)
    normals = normal_values(surface,.033,.110,periodic=False)
    save_png("weapon_walnut_normal.png",normals)
    # Geometry assigns this to a sparse, asymmetrical subset of flattened tooth
    # tips. It is not spread uniformly over every diamond or the groove bed.
    worn = np.array([76.,47.,35.],dtype=np.float32)[None,None,:]
    worn = worn + tone[...,None]*np.array([1.,.75,.61],dtype=np.float32)
    worn *= 1-pores[...,None]*.13
    worn_rough = np.clip(.456-handled*.025+broad*.024+pores*.047,.37,.53)
    save_color("weapon_walnut_worn_albedo.png",worn)
    save_scalar("weapon_walnut_worn_roughness.png",worn_rough)
    save_png("weapon_walnut_worn_normal.png",normals)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    steel()
    brushed()
    walnut()
    slide()
    frame()
    print("Generated 21 original reference-finish pistol PBR maps in", OUTPUT)
