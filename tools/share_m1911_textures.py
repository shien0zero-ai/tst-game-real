#!/usr/bin/env python3
"""Externalize identical Blender GLB images without recompressing their pixels.

Run after the Blender export and before Godot imports the model components.
Only the Python standard library is required. Existing external images are checked
but their GLBs are left byte-for-byte unchanged on subsequent runs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import Any, Iterable
from urllib.parse import quote, unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("slide", "frame", "magazine")
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
UNSUPPORTED_EXTENSIONS = {"KHR_draco_mesh_compression", "EXT_meshopt_compression"}


class GlbError(ValueError):
    """An input is outside the supported, single-buffer GLB subset."""


@dataclass
class Glb:
    document: dict[str, Any]
    binary: bytes


@dataclass
class Texture:
    path: Path
    data: bytes
    sha256: str


@dataclass
class Plan:
    path: Path
    original: bytes
    replacement: bytes | None
    images: int
    geometry_sha256: str


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise GlbError(f"{label} must be an integer >= {minimum}")
    return value


def _walk(value: Any, path: tuple = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path + (key,), child
            yield from _walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, path + (index,))


def _parse(data: bytes) -> Glb:
    if len(data) < 20:
        raise GlbError("Truncated GLB header")
    magic, version, length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise GlbError("Expected a complete GLB version 2 file")
    offset, chunks = 12, []
    while offset < len(data):
        if offset + 8 > len(data):
            raise GlbError("Truncated GLB chunk header")
        size, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        if size % 4 or offset + size > len(data):
            raise GlbError("Invalid GLB chunk length/alignment")
        chunks.append((kind, data[offset:offset + size]))
        offset += size
    if [kind for kind, _ in chunks] != [JSON_CHUNK, BIN_CHUNK]:
        raise GlbError("Only one JSON chunk followed by one BIN chunk is supported")
    try:
        document = json.loads(chunks[0][1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GlbError(f"Invalid GLB JSON: {error}") from error
    if not isinstance(document, dict) or document.get("asset", {}).get("version") != "2.0":
        raise GlbError("Expected glTF asset version 2.0")
    buffers = document.get("buffers", [])
    if len(buffers) != 1 or not isinstance(buffers[0], dict) or "uri" in buffers[0]:
        raise GlbError("Only a single embedded buffer is supported")
    binary_length = _integer(buffers[0].get("byteLength"), "buffer.byteLength")
    binary = chunks[1][1]
    if not binary_length <= len(binary) <= binary_length + 3:
        raise GlbError("BIN chunk and buffer.byteLength disagree")
    for path, value in _walk(document):
        if path[-1] in ("extensionsUsed", "extensionsRequired"):
            if not isinstance(value, list):
                raise GlbError(f"Invalid extension list: {path}")
            if UNSUPPORTED_EXTENSIONS.intersection(value):
                raise GlbError("Draco/meshopt compression is not supported")
        if path[-1] == "extensions" and isinstance(value, dict):
            if UNSUPPORTED_EXTENSIONS.intersection(value):
                raise GlbError("Draco/meshopt compression is not supported")
    views = document.get("bufferViews", [])
    if not isinstance(views, list):
        raise GlbError("bufferViews must be an array")
    for index, view in enumerate(views):
        if not isinstance(view, dict) or view.get("buffer") != 0:
            raise GlbError(f"bufferView {index} is not in embedded buffer 0")
        start = _integer(view.get("byteOffset", 0), f"bufferView {index}.byteOffset")
        size = _integer(view.get("byteLength"), f"bufferView {index}.byteLength", 1)
        if start + size > binary_length:
            raise GlbError(f"bufferView {index} exceeds its buffer")
    for path, index in _walk(document):
        if path[-1] == "bufferView":
            _integer(index, f"bufferView reference {path}")
            if index >= len(views):
                raise GlbError(f"bufferView reference {path} is out of range")
    return Glb(document, binary[:binary_length])


def _view_bytes(glb: Glb, index: int) -> bytes:
    view = glb.document["bufferViews"][index]
    start = view.get("byteOffset", 0)
    return glb.binary[start:start + view["byteLength"]]


def _image_type(image: dict, data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime, extension = "image/png", "png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime, extension = "image/jpeg", "jpg"
    else:
        raise GlbError("Only embedded PNG and JPEG images are supported")
    if image.get("mimeType") != mime:
        raise GlbError("Embedded image MIME type does not match its bytes")
    return extension


def _external_image(model: Path, image: dict) -> Path:
    uri = image.get("uri")
    if not isinstance(uri, str):
        raise GlbError("An external image must have a URI")
    parsed = urlsplit(uri)
    local = Path(unquote(parsed.path))
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or local.is_absolute() or "\\" in uri):
        raise GlbError(f"Only relative local image URIs are supported: {uri}")
    target = (model.parent / local).resolve()
    if not target.is_file():
        raise GlbError(f"External image does not exist: {target}")
    return target


def _texture(image: dict, data: bytes, output: Path, textures: dict[str, Texture]) -> Texture:
    extension = _image_type(image, data)
    digest = hashlib.sha256(data).hexdigest()
    if digest in textures:
        return textures[digest]
    name = re.sub(r"[^a-z0-9._-]+", "_", str(image.get("name", "m1911")).lower())
    name = name.strip("._-")[:64] or "m1911"
    target = output / f"{name}-{digest[:20]}.{extension}"
    # Reuse an extraction made by an earlier partial build, even if the source
    # image has since been renamed. Never trust a filename without its hash.
    for candidate in sorted(output.glob(f"*-{digest[:20]}.{extension}")):
        if candidate.is_file() and hashlib.sha256(candidate.read_bytes()).hexdigest() == digest:
            target = candidate
            break
    if target.exists() and target.read_bytes() != data:
        raise GlbError(f"Texture filename collision: {target}")
    texture = Texture(target, data, digest)
    textures[digest] = texture
    return texture


def _encode(glb: Glb) -> bytes:
    encoded = json.dumps(glb.document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    binary = glb.binary + b"\0" * (-len(glb.binary) % 4)
    total = 12 + 8 + len(encoded) + 8 + len(binary)
    return (struct.pack("<4sII", b"glTF", 2, total)
            + struct.pack("<II", len(encoded), JSON_CHUNK) + encoded
            + struct.pack("<II", len(binary), BIN_CHUNK) + binary)


def _geometry_digest(payloads: Iterable[bytes]) -> str:
    digest = hashlib.sha256()
    for payload in payloads:
        digest.update(struct.pack("<Q", len(payload)))
        digest.update(payload)
    return digest.hexdigest()


def _plan(path: Path, output: Path, textures: dict[str, Texture]) -> Plan:
    original = path.read_bytes()
    glb = _parse(original)
    document = glb.document
    images = document.get("images", [])
    if not isinstance(images, list) or any(not isinstance(image, dict) for image in images):
        raise GlbError("images must be an array of image objects")
    embedded = set()
    embedded_count = 0
    for image in images:
        if "bufferView" in image:
            if "uri" in image:
                raise GlbError("An image cannot have both bufferView and URI")
            embedded.add(image["bufferView"])
            embedded_count += 1
        else:
            _external_image(path, image)
    views = document.get("bufferViews", [])
    kept = [index for index in range(len(views)) if index not in embedded]
    for reference, index in _walk(document):
        if reference[-1] == "bufferView" and reference[0] != "images" and index in embedded:
            raise GlbError(f"Image bufferView {index} is also referenced by {reference}")
    for image_index in embedded:
        image_view = views[image_index]
        image_start = image_view.get("byteOffset", 0)
        image_end = image_start + image_view["byteLength"]
        for geometry_index in kept:
            view = views[geometry_index]
            start = view.get("byteOffset", 0)
            if image_start < start + view["byteLength"] and start < image_end:
                raise GlbError(f"Image bufferView {image_index} overlaps bufferView {geometry_index}")
    before = [_view_bytes(glb, index) for index in kept]
    geometry_sha256 = _geometry_digest(before)
    if not embedded:
        return Plan(path, original, None, 0, geometry_sha256)

    for image in images:
        if "bufferView" not in image:
            continue
        texture = _texture(image, _view_bytes(glb, image["bufferView"]), output, textures)
        relative = Path(os.path.relpath(texture.path, path.parent)).as_posix()
        image["uri"] = quote(relative, safe="/-._~")
        del image["bufferView"]
        del image["mimeType"]

    remap = {old: new for new, old in enumerate(kept)}
    binary = bytearray()
    new_views = []
    for old in kept:
        view = views[old].copy()
        binary.extend(b"\0" * (-len(binary) % 4))
        view["byteOffset"] = len(binary)
        binary.extend(_view_bytes(glb, old))
        new_views.append(view)
    document["bufferViews"] = new_views
    document["buffers"][0]["byteLength"] = len(binary)

    def remap_references(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "bufferView":
                    if child not in remap:
                        raise GlbError(f"Unmapped bufferView reference: {child}")
                    value[key] = remap[child]
                else:
                    remap_references(child)
        elif isinstance(value, list):
            for child in value:
                remap_references(child)

    remap_references(document)
    replacement = _encode(Glb(document, bytes(binary)))
    checked = _parse(replacement)
    after = [_view_bytes(checked, index) for index in range(len(kept))]
    if before != after or _geometry_digest(after) != geometry_sha256:
        raise GlbError("Geometry bufferView payloads changed during extraction")
    return Plan(path, original, replacement, embedded_count, geometry_sha256)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def externalize_models(model_paths: Iterable[Path], output_dir: Path) -> list[Plan]:
    """Validate all inputs, then atomically replace each GLB and share its images.

    Raises GlbError before replacing any GLB when input validation fails. Textures
    are never recompressed or deleted. A caller may inspect the returned plans
    for byte counts and the digest of unchanged non-image bufferView payloads.
    """
    output = Path(output_dir).resolve()
    paths = sorted({Path(path).resolve() for path in model_paths})
    textures: dict[str, Texture] = {}
    plans = []
    for path in paths:
        try:
            plans.append(_plan(path, output, textures))
        except (GlbError, OSError) as error:
            raise GlbError(f"{path.name}: {error}") from error
    for texture in textures.values():
        if not texture.path.exists():
            _atomic_write(texture.path, texture.data)
        if texture.path.read_bytes() != texture.data:
            raise GlbError(f"Extracted image bytes do not match: {texture.path}")
    # Check every URI after the planned textures exist, before replacing a GLB.
    for plan in plans:
        if plan.replacement is not None:
            for image in _parse(plan.replacement).document.get("images", []):
                _external_image(plan.path, image)
        if plan.path.read_bytes() != plan.original:
            raise GlbError(f"Input changed while planning: {plan.path}")
    for plan in plans:
        if plan.replacement is not None:
            _atomic_write(plan.path, plan.replacement)
    return plans


def share_textures(models_dir: Path | None = None, output_dir: Path | None = None) -> list[Plan]:
    """Externalize three M1911 component GLBs; the grip is part of the frame."""
    models = Path(models_dir) if models_dir is not None else ROOT / "assets" / "models"
    output = Path(output_dir) if output_dir is not None else ROOT / "assets" / "textures" / "m1911_runtime"
    return externalize_models((models / f"m1911_{name}.glb" for name in COMPONENTS), output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=ROOT / "assets" / "models")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets" / "textures" / "m1911_runtime")
    arguments = parser.parse_args()
    try:
        plans = share_textures(arguments.models_dir, arguments.output_dir)
    except (GlbError, OSError) as error:
        parser.exit(1, f"Texture sharing failed: {error}\n")
    for plan in plans:
        size = len(plan.replacement) if plan.replacement is not None else len(plan.original)
        print(f"{plan.path.name}: {len(plan.original):,} -> {size:,} bytes; "
              f"{plan.images} images externalized; geometry SHA256 {plan.geometry_sha256}")


if __name__ == "__main__":
    main()
