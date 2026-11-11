#!/usr/bin/env python3
"""Normalize the credited tactical guard and retarget its Mixamo animation clips.

Usage: python tools/adapt_raid_assets.py tactical.glb animated_soldier.glb enemy.glb
       python tools/adapt_raid_assets.py --prop source.glb output.glb
Requires numpy and Pillow. Source downloads / hashes are documented in
tools/source_assets/raid/models-manifest.json and licenses/raid/THIRD_PARTY.txt.
The output uses ordinary float accessors, embedded PNGs, and no compression extension.
"""
import argparse
import copy
import io
import json
import os
import re
import struct
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


COMPONENTS = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class GLB:
    def __init__(self, path):
        data = Path(path).read_bytes()
        assert data[:4] == b"glTF"
        size, tag = struct.unpack_from("<II", data, 12)
        assert tag == 0x4E4F534A
        self.doc = json.loads(data[20:20 + size])
        self.binary = data[28 + size:]

    def accessor(self, index):
        a = self.doc["accessors"][index]
        v = self.doc["bufferViews"][a["bufferView"]]
        dtype = np.dtype(COMPONENTS[a["componentType"]])
        assert "sparse" not in a
        return np.ndarray((a["count"], WIDTH[a["type"]]), dtype=dtype,
                          buffer=self.binary,
                          offset=v.get("byteOffset", 0) + a.get("byteOffset", 0),
                          strides=(v.get("byteStride", dtype.itemsize * WIDTH[a["type"]]), dtype.itemsize)).copy()

    def image(self, index):
        a = self.doc["images"][index]
        v = self.doc["bufferViews"][a["bufferView"]]
        return self.binary[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]]


def rotation(q):
    x, y, z, w = q
    return np.array([[1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
                     [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
                     [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y]])


def quaternion(m):
    # Eigenvector form avoids numerical trouble around 180 degree rotations.
    q = np.array([[m[0, 0]-m[1, 1]-m[2, 2], m[0, 1]+m[1, 0], m[0, 2]+m[2, 0], m[2, 1]-m[1, 2]],
                  [m[0, 1]+m[1, 0], m[1, 1]-m[0, 0]-m[2, 2], m[1, 2]+m[2, 1], m[0, 2]-m[2, 0]],
                  [m[0, 2]+m[2, 0], m[1, 2]+m[2, 1], m[2, 2]-m[0, 0]-m[1, 1], m[1, 0]-m[0, 1]],
                  [m[2, 1]-m[1, 2], m[0, 2]-m[2, 0], m[1, 0]-m[0, 1], m.trace()]]) / 3
    values, vectors = np.linalg.eigh(q)
    result = vectors[:, np.argmax(values)]
    return result if result[3] >= 0 else -result


def multiply(a, b):
    av, bv = np.array(a[:3]), np.array(b[:3])
    return np.r_[a[3]*bv + b[3]*av + np.cross(av, bv), a[3]*b[3] - av.dot(bv)]


def matrix(node):
    if "matrix" in node:
        return np.array(node["matrix"]).reshape(4, 4).T
    result = np.eye(4)
    result[:3, :3] = rotation(node.get("rotation", [0, 0, 0, 1])) @ np.diag(node.get("scale", [1, 1, 1]))
    result[:3, 3] = node.get("translation", [0, 0, 0])
    return result


def key(name):
    return re.sub(r"_\d+$", "", re.sub(r"^mixamorig:?", "", name))


class Writer:
    def __init__(self):
        self.doc = {"asset": {"version": "2.0", "generator": "tst-game-real raid asset adapter"},
                    "buffers": [{}], "bufferViews": [], "accessors": [], "nodes": [], "meshes": [],
                    "materials": [], "textures": [], "images": [], "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]}
        self.binary = bytearray()

    def view(self, data):
        self.binary.extend(b"\0" * (-len(self.binary) % 4))
        index = len(self.doc["bufferViews"])
        self.doc["bufferViews"].append({"buffer": 0, "byteOffset": len(self.binary), "byteLength": len(data)})
        self.binary.extend(data)
        return index

    def accessor(self, data, kind, component=5126):
        data = np.asarray(data, dtype=COMPONENTS[component])
        index = len(self.doc["accessors"])
        a = {"bufferView": self.view(data.tobytes()), "componentType": component,
             "count": len(data), "type": kind}
        if kind in ("VEC3", "SCALAR"):
            a.update(min=data.reshape(len(data), -1).min(0).tolist(), max=data.reshape(len(data), -1).max(0).tolist())
        self.doc["accessors"].append(a)
        return index

    def save(self, path):
        self.doc["buffers"][0]["byteLength"] = len(self.binary)
        js = json.dumps(self.doc, separators=(",", ":")).encode()
        js += b" " * (-len(js) % 4)
        self.binary.extend(b"\0" * (-len(self.binary) % 4))
        result = struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(self.binary))
        result += struct.pack("<II", len(js), 0x4E4F534A) + js
        result += struct.pack("<II", len(self.binary), 0x004E4942) + self.binary
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".raid-", suffix=".tmp", dir=Path(path).parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(result)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)


def pistol_support_hand(writer, named):
    """Bake a two-bone support-arm solve into the three aim clips."""
    doc = writer.doc
    parents = {c: i for i, n in enumerate(doc["nodes"]) for c in n.get("children", [])}
    arm, fore, hand, right = (named[n] for n in ("LeftArm", "LeftForeArm", "LeftHand", "RightHand"))
    def read(index):
        a = doc["accessors"][index]; v = doc["bufferViews"][a["bufferView"]]
        return np.frombuffer(writer.binary, dtype=COMPONENTS[a["componentType"]], count=a["count"]*WIDTH[a["type"]],
                             offset=v["byteOffset"]).reshape(a["count"], WIDTH[a["type"]]).copy()
    def turn(a, b):
        a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
        q = np.r_[np.cross(a, b), 1 + np.dot(a, b)]
        return rotation(q / np.linalg.norm(q))
    for clip in doc["animations"]:
        if not clip["name"].startswith("aim_"): continue
        tracks = []
        for channel in clip["channels"]:
            sampler = clip["samplers"][channel["sampler"]]
            tracks.append((channel["target"]["node"], channel["target"]["path"], read(sampler["input"])[:, 0], read(sampler["output"])))
        times = sorted(set(float(t) for _, _, keys, _ in tracks for t in keys))
        solved = {arm: [], fore: [], hand: []}
        for time in times:
            nodes = copy.deepcopy(doc["nodes"])
            for node, path, keys, values in tracks:
                upper = min(int(np.searchsorted(keys, time, side="right")), len(keys)-1)
                lower = max(upper-1, 0)
                fraction = 0 if keys[upper] == keys[lower] else np.clip((time-keys[lower])/(keys[upper]-keys[lower]), 0, 1)
                a, b = values[lower], values[upper]
                if path == "rotation" and a.dot(b) < 0: b = -b
                value = a*(1-fraction) + b*fraction
                if path == "rotation": value /= np.linalg.norm(value)
                nodes[node][path] = value.tolist()
            def world(index):
                local = matrix(nodes[index])
                return world(parents[index]) @ local if index in parents else local
            shoulder, elbow, wrist = (world(i)[:3, 3] for i in (arm, fore, hand))
            # Match the firing-hand finger direction while opposing the palms.
            wrist_rotation = world(right)[:3, :3] @ np.diag([-1., 1., -1.])
            target = world(right)[:3, 3] + np.array([.018, -.030, .018])
            upper_length, lower_length = np.linalg.norm(elbow-shoulder), np.linalg.norm(wrist-elbow)
            ray = target-shoulder; distance = np.clip(np.linalg.norm(ray), abs(upper_length-lower_length)+.001, upper_length+lower_length-.001)
            ray /= np.linalg.norm(ray)
            bend = elbow-shoulder-ray*np.dot(elbow-shoulder, ray); bend /= np.linalg.norm(bend)
            along = (upper_length**2-lower_length**2+distance**2)/(2*distance)
            desired_elbow = shoulder+ray*along+bend*np.sqrt(max(0, upper_length**2-along**2))
            desired_upper = turn(elbow-shoulder, desired_elbow-shoulder) @ world(arm)[:3, :3]
            nodes[arm]["rotation"] = quaternion(np.linalg.inv(world(parents[arm])[:3, :3]) @ desired_upper).tolist()
            elbow, wrist = world(fore)[:3, 3], world(hand)[:3, 3]
            desired_fore = turn(wrist-elbow, target-elbow) @ world(fore)[:3, :3]
            nodes[fore]["rotation"] = quaternion(np.linalg.inv(world(parents[fore])[:3, :3]) @ desired_fore).tolist()
            nodes[hand]["rotation"] = quaternion(np.linalg.inv(world(fore)[:3, :3]) @ wrist_rotation).tolist()
            for joint in solved:
                q = np.array(nodes[joint]["rotation"])
                if solved[joint] and np.dot(q, solved[joint][-1]) < 0: q = -q
                solved[joint].append(q)
        for channel in clip["channels"]:
            target = channel["target"]
            if target["path"] == "rotation" and target["node"] in solved:
                sampler = clip["samplers"][channel["sampler"]]
                sampler["input"] = writer.accessor(np.array(times).reshape(-1, 1), "SCALAR")
                sampler["output"] = writer.accessor(solved[target["node"]], "VEC4")


def normalize(tactical, animated, output):
    tac, src, out = GLB(tactical), GLB(animated), Writer()
    td, sd, od = tac.doc, src.doc, out.doc
    joints = td["skins"][0]["joints"]
    ibm = tac.accessor(td["skins"][0]["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
    parent = {c: i for i, n in enumerate(td["nodes"]) for c in n.get("children", [])}
    # The source's bind matrices counteract million-unit mesh coordinates. Bake
    # that scale into vertices and reconstruct a conventional metre-based rig.
    bind = [np.diag([1e-6, 1e-6, 1e-6, 1.0]) @ np.linalg.inv(m) for m in ibm]
    bind[0] = np.eye(4)  # unused exporter root, its identity IBM is not a bone bind
    for transform in bind:
        # Pouch helper joints carry centimetre scale in otherwise metre-based
        # binds. Remove it in world space before rebuilding local bone transforms.
        transform[:3, :3] /= np.linalg.norm(transform[:3, :3], axis=0)
    joint_map = {n: i for i, n in enumerate(joints)}
    named = {key(td["nodes"][n]["name"]): i for i, n in enumerate(joints)}
    for i, original in enumerate(joints):
        p = parent.get(original)
        while p is not None and p not in joint_map:
            p = parent.get(p)
        local = np.linalg.inv(bind[joint_map[p]]) @ bind[i] if p in joint_map else bind[i]
        scale = np.linalg.norm(local[:3, :3], axis=0)
        od["nodes"].append({"name": key(td["nodes"][original]["name"]).replace("_rootJoint", "Root"),
                            "translation": local[:3, 3].tolist(),
                            "rotation": quaternion(local[:3, :3] / scale).tolist()})
        if p in joint_map:
            od["nodes"][joint_map[p]].setdefault("children", []).append(i)
    od["skins"] = [{"name": "RaidGuardRig", "joints": list(range(len(joints))), "skeleton": 0,
                    "inverseBindMatrices": out.accessor(np.array([np.linalg.inv(m).T.reshape(16) for m in bind]), "MAT4")}]

    # Preserve seven source PBR materials; discard floating headset material/mesh.
    od["materials"] = copy.deepcopy(td["materials"])
    texture_used = set()
    normal_textures = set()
    scalar_textures = set()
    for mat in od["materials"][:-1]:
        mat.pop("extensions", None)
        if "normalTexture" in mat: normal_textures.add(mat["normalTexture"]["index"])
        pbr = mat.get("pbrMetallicRoughness", {})
        if "metallicRoughnessTexture" in pbr: scalar_textures.add(pbr["metallicRoughnessTexture"]["index"])
        def gather(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k.endswith("Texture") and isinstance(v, dict): texture_used.add(v["index"])
                    else: gather(v)
        gather(mat)
    texture_map = {}
    for old in sorted(texture_used):
        tex = td["textures"][old]
        image_index = tex.get("source", tex.get("extensions", {}).get("EXT_texture_webp", {}).get("source"))
        image = Image.open(io.BytesIO(tac.image(image_index))).convert("RGB")
        limit = 256 if old in scalar_textures or old in normal_textures else 512
        image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
        if old in normal_textures:
            vectors = np.asarray(image, dtype=np.float32) / 127.5 - 1
            vectors /= np.maximum(np.linalg.norm(vectors, axis=2, keepdims=True), 1e-6)
            image = Image.fromarray(np.rint((vectors + 1) * 127.5).clip(0, 255).astype(np.uint8))
        data = io.BytesIO(); image.save(data, "PNG", optimize=True)
        new = len(od["textures"])
        texture_map[old] = new
        od["textures"].append({"sampler": 0, "source": new})
        od["images"].append({"name": f"TacticalPBR{new}", "mimeType": "image/png", "bufferView": out.view(data.getvalue())})
    def remap(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.endswith("Texture") and isinstance(v, dict): v["index"] = texture_map[v["index"]]
                else: remap(v)
    od["materials"].pop()  # removed headset
    for mat in od["materials"]: remap(mat)

    root_children = [0]
    for mesh_index, mesh in enumerate(td["meshes"]):
        if any(p.get("material") == 6 for p in mesh["primitives"]):
            continue  # source's separate headset floats above the cap
        new_mesh = {"name": mesh.get("name", f"GuardPart{mesh_index}"), "primitives": []}
        for primitive in mesh["primitives"]:
            attributes = {}
            for name, index in primitive["attributes"].items():
                a = td["accessors"][index]
                values = tac.accessor(index)
                if name == "POSITION":
                    if mesh_index == 0:
                        eye = matrix(td["nodes"][14])
                        values = (bind[named["Head"]] @ eye @ np.c_[values, np.ones(len(values))].T).T[:, :3]
                    else:
                        values *= 1e-6
                elif name in ("NORMAL", "TANGENT") and mesh_index == 0:
                    values[:, :3] = (bind[named["Head"]][:3, :3] @ rotation(td["nodes"][14]["rotation"]) @ values[:, :3].T).T
                attributes[name] = out.accessor(values, a["type"], a["componentType"])
            if mesh_index == 0:
                count = td["accessors"][primitive["attributes"]["POSITION"]]["count"]
                joint_values = np.zeros((count, 4)); joint_values[:, 0] = named["Head"]
                weight_values = np.zeros((count, 4)); weight_values[:, 0] = 1
                attributes["JOINTS_0"] = out.accessor(joint_values, "VEC4", 5123)
                attributes["WEIGHTS_0"] = out.accessor(weight_values, "VEC4")
            indices = tac.accessor(primitive["indices"])
            new_mesh["primitives"].append({"attributes": attributes, "material": primitive["material"],
                                            "indices": out.accessor(indices, "SCALAR", 5125)})
        od["meshes"].append(new_mesh)
        root_children.append(len(od["nodes"]))
        od["nodes"].append({"name": f"GuardMesh{mesh_index}", "mesh": len(od["meshes"])-1, "skin": 0})

    src_parents = {c: i for i, n in enumerate(sd["nodes"]) for c in n.get("children", [])}
    source_named = {key(n.get("name", "")): i for i, n in enumerate(sd["nodes"])}
    def source_world(index):
        local = matrix(sd["nodes"][index])
        return source_world(src_parents[index]) @ local if index in src_parents else local
    sh = source_named["Hips"]
    source_parent = source_world(src_parents[sh])
    parent_rotation = source_parent[:3, :3] / np.linalg.norm(source_parent[:3, :3], axis=0)
    hip_rotation = quaternion(parent_rotation)
    source_leg = source_world(sh)[1, 3] - source_world(source_named["LeftFoot"])[1, 3]
    dest_leg = bind[named["Hips"]][1, 3] - bind[named["LeftFoot"]][1, 3]
    ratio = dest_leg / source_leg
    selected = {"aim_idle", "aim_walk", "aim_run", "idle", "walk", "run", "death", "hit", "reload"}
    od["animations"] = []
    for clip in sd["animations"]:
        if clip["name"] not in selected: continue
        animation = {"name": clip["name"], "samplers": [], "channels": []}
        for channel in clip["channels"]:
            target = channel["target"]
            name = key(sd["nodes"][target["node"]]["name"])
            path = target["path"]
            if name not in named or path == "scale" or (path == "translation" and name != "Hips"): continue
            sampler = clip["samplers"][channel["sampler"]]
            values = src.accessor(sampler["output"])
            if name == "Hips":
                if path == "rotation": values = np.array([multiply(hip_rotation, q) for q in values])
                else: values = (source_parent @ np.c_[values, np.ones(len(values))].T).T[:, :3] * ratio
            s = len(animation["samplers"])
            animation["samplers"].append({"input": out.accessor(src.accessor(sampler["input"]), "SCALAR"),
                                          "output": out.accessor(values, "VEC4" if path == "rotation" else "VEC3"),
                                          "interpolation": sampler.get("interpolation", "LINEAR")})
            animation["channels"].append({"sampler": s, "target": {"node": named[name], "path": path}})
        od["animations"].append(animation)
    pistol_support_hand(out, named)
    height = max(tac.accessor(p["attributes"]["POSITION"])[:, 1].max() * 1e-6
                 for i, mesh in enumerate(td["meshes"]) if i not in (0, 8) for p in mesh["primitives"])
    root = len(od["nodes"])
    od["nodes"].append({"name": "RaidTacticalGuard", "rotation": [0, 1, 0, 0],
                        "scale": [float(1.72/height)]*3, "children": root_children,
                        "extras": {"author": "DanlyVostok; BAMEN; Quaternius", "license": "CC BY 4.0; CC0",
                                   "forward": "-Z", "units": "metres", "right_hand_bone": "RightHand"}})
    od["scenes"] = [{"name": "RaidTacticalGuard", "nodes": [root]}]
    od["scene"] = 0
    out.save(output)
    print(json.dumps({"file": str(output), "bytes": Path(output).stat().st_size, "height": 1.72,
                      "facing": "-Z", "bones": len(joints), "animations": [a["name"] for a in od["animations"]]}, indent=2))


def normalize_prop(source, output):
    """Embed ordinary PNG images in an already uncompressed public prop GLB."""
    original, writer = GLB(source), Writer()
    writer.doc = copy.deepcopy(original.doc)
    writer.binary = bytearray(original.binary)
    for image in writer.doc.get("images", []):
        view = original.doc["bufferViews"][image["bufferView"]]
        raw = original.binary[view.get("byteOffset", 0):view.get("byteOffset", 0) + view["byteLength"]]
        data = io.BytesIO()
        picture = Image.open(io.BytesIO(raw))
        picture.thumbnail((512, 512), Image.Resampling.LANCZOS)
        picture.save(data, "PNG", optimize=True)
        image.update(mimeType="image/png", bufferView=writer.view(data.getvalue()))
    for texture in writer.doc.get("textures", []):
        extension = texture.get("extensions", {}).pop("EXT_texture_webp", None)
        if extension: texture["source"] = extension["source"]
        if not texture.get("extensions"): texture.pop("extensions", None)
    for field in ("extensionsUsed", "extensionsRequired"):
        if field in writer.doc:
            writer.doc[field] = [x for x in writer.doc[field] if x != "EXT_texture_webp"]
            if not writer.doc[field]: writer.doc.pop(field)
    assert "EXT_meshopt_compression" not in writer.doc.get("extensionsUsed", [])
    writer.doc["asset"]["generator"] = "tst-game-real raid PNG adapter"
    writer.save(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prop", action="store_true")
    parser.add_argument("tactical")
    parser.add_argument("animated")
    parser.add_argument("output", nargs="?")
    args = parser.parse_args()
    if args.prop:
        normalize_prop(args.tactical, args.animated)
    else:
        if args.output is None: parser.error("enemy conversion requires three paths")
        normalize(args.tactical, args.animated, args.output)
