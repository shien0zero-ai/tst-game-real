#!/usr/bin/env python3
"""Export a portable Windows game on Linux, with Japanese play instructions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "4.6.3"
TEMPLATE_VERSION = VERSION + ".stable"
NAME = "M1911-FiringRange-Windows-x86_64"


def run_engine(engine: str, arguments: list[str], env: dict[str, str], log: Path) -> None:
    result = subprocess.run([engine, *arguments], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log.write_text(result.stdout, encoding="utf-8")
    print(result.stdout, end="")
    if result.returncode or "SCRIPT ERROR:" in result.stdout or "ERROR:" in result.stdout:
        raise RuntimeError(f"Godot export failed; see {log}")


def validate_windows_executable(path: Path) -> None:
    with path.open("rb") as file:
        if file.read(2) != b"MZ":
            raise RuntimeError("Export is not a Windows executable")
        file.seek(0x3C)
        pe_offset = struct.unpack("<I", file.read(4))[0]
        file.seek(pe_offset)
        if file.read(4) != b"PE\0\0" or struct.unpack("<H", file.read(2))[0] != 0x8664:
            raise RuntimeError("Export is not a Windows x86-64 PE executable")
        file.seek(-4, os.SEEK_END)
        if file.read(4) != b"GDPC":
            raise RuntimeError("Embedded game data is missing from the executable")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default=shutil.which("godot") or shutil.which("godot4"))
    parser.add_argument("--templates-dir", type=Path,
                        help="Directory containing official 4.6.3 export template files")
    args = parser.parse_args()
    if not args.godot:
        parser.error("Godot 4.6.3 is required to build; players do not need Godot.")

    runtime = ROOT / "work" / "godot"
    env = os.environ.copy()
    for suffix in ("cache", "config", "data"):
        directory = runtime / suffix
        directory.mkdir(parents=True, exist_ok=True)
        env[f"XDG_{suffix.upper()}_HOME"] = str(directory)
    (ROOT / "work" / ".gdignore").touch()
    engine_version = subprocess.check_output([args.godot, "--version"], env=env, text=True).strip()
    if not engine_version.startswith(VERSION + ".stable."):
        parser.error(f"Use Godot {VERSION} to match the export templates; found {engine_version}")

    destination = runtime / "data" / "godot" / "export_templates" / TEMPLATE_VERSION
    candidates = [destination, ROOT / "work" / "export-templates"]
    if args.templates_dir:
        candidates.insert(0, args.templates_dir.resolve())
    # Read templates already installed through Godot's template manager, if available.
    for data_home in (os.environ.get("XDG_DATA_HOME"), str(Path.home() / ".local" / "share"),
                      os.environ.get("APPDATA"), str(Path.home() / "Library" / "Application Support")):
        if data_home:
            candidates.extend(Path(data_home) / case / "export_templates" / TEMPLATE_VERSION
                              for case in ("godot", "Godot"))
    source = next((p for p in candidates if (p / "windows_release_x86_64.exe").is_file()), None)
    if source is None:
        parser.error("Install Godot 4.6.3 export templates, or use --templates-dir DIRECTORY.")
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ("windows_release_x86_64.exe", "windows_release_x86_64_console.exe", "linux_release.x86_64"):
        original = source / filename
        target = destination / filename
        if original.is_file() and original.resolve() != target.resolve():
            shutil.copy2(original, target)
    (destination / "version.txt").write_text(TEMPLATE_VERSION + "\n", encoding="utf-8")

    executable = ROOT / "build" / "windows" / "M1911-FiringRange.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    run_engine(args.godot, ["--headless", "--path", str(ROOT), "--editor", "--quit"],
               env, runtime / "windows-import.log")
    run_engine(args.godot, ["--headless", "--path", str(ROOT), "--export-release",
                           "Windows Desktop", str(executable)], env, runtime / "windows-export.log")
    validate_windows_executable(executable)
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    source_status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", ".", ":(exclude)downloads/"],
        cwd=ROOT, text=True)
    info = {"game": "M1911 Firing Range", "platform": "Windows x86_64", "renderer": "Compatibility",
            "engine": engine_version, "source_commit": source_commit,
            "source_dirty": bool(source_status.strip()),
            "exe_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()}
    downloads = ROOT / "downloads"
    downloads.mkdir(exist_ok=True)
    archive = downloads / (NAME + ".zip")
    temporary = archive.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            output.write(executable, executable.name)
            output.write(ROOT / "docs" / "PLAY-WINDOWS.txt", "PLAY-WINDOWS.txt")
            for license_path in sorted((ROOT / "licenses" / "godot").glob("*.txt")):
                output.write(license_path, f"licenses/{license_path.name}")
            output.writestr("build-info.json", json.dumps(info, ensure_ascii=False, indent=2) + "\n")
        with zipfile.ZipFile(temporary) as package:
            bad = package.testzip()
            if bad:
                raise RuntimeError("ZIP integrity check failed: " + bad)
        if temporary.stat().st_size >= 100 * 1024 * 1024:
            raise RuntimeError("ZIP exceeds GitHub's normal file size limit")
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(f"Portable Windows game: {archive} ({archive.stat().st_size:,} bytes)")
    print("No Godot installation is required on the player's PC.")


if __name__ == "__main__":
    main()
