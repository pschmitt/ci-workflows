#!/usr/bin/env python3
"""Build and validate `fdroid-metadata.zip` from an app's `fdroid/` directory.

The archive is read by the F-Droid publisher (schema 1, see docs/fdroid-metadata.md).
The limits and allowlist below mirror the publisher's importer, so a problem fails
the app's release build instead of being ignored in production.

Source layout (one directory per package):

    fdroid/<package>/metadata.yml
    fdroid/<package>/icon.png        optional

Archive layout:

    manifest.yml                          schema: 1
    metadata/<package>/metadata.yml
    metadata/<package>/en-US/icon.png
"""

from __future__ import annotations

import os
import re
import stat
import struct
import sys
import zipfile
from pathlib import Path

import yaml

SCHEMA = 1
ARCHIVE = "fdroid-metadata.zip"
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 64
MAX_YAML_BYTES = 64 * 1024
MAX_ICON_BYTES = 1024 * 1024
ICON_PIXELS = (48, 1024)
PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")
LICENSE = re.compile(r"[A-Za-z0-9.+-]+(?: (?:AND|OR|WITH) [A-Za-z0-9.+-]+)*")
CATEGORIES = {
    "Connectivity", "Development", "Games", "Graphics", "Internet", "Money", "Multimedia",
    "Navigation", "Phone & SMS", "Reading", "Science & Education", "Security", "Sports & Health",
    "System", "Theming", "Time", "Writing",
}
TEXT_LIMITS = {"name": 50, "summary": 80, "description": 4000}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EPOCH = (1980, 1, 1, 0, 0, 0)


def check_metadata(raw: bytes) -> None:
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("must be a mapping")
    unknown = sorted(set(data) - set(TEXT_LIMITS) - {"license", "categories"})
    if unknown:
        raise ValueError(f"unknown field(s): {', '.join(map(str, unknown))}")
    for field, limit in TEXT_LIMITS.items():
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"{field} must be a non-empty string of at most {limit} characters")
        if any((ord(c) < 32 and c not in "\n\t") or ord(c) == 127 for c in value):
            raise ValueError(f"{field} contains control characters")
    if "license" in data:
        value = data["license"]
        if not isinstance(value, str) or len(value) > 64 or not LICENSE.fullmatch(value):
            raise ValueError("license must be an SPDX identifier or expression")
    if "categories" in data:
        value = data["categories"]
        if (not isinstance(value, list) or not 1 <= len(value) <= 3
                or any(c not in CATEGORIES for c in value) or len(set(value)) != len(value)):
            raise ValueError("categories must be one to three distinct F-Droid categories")


def check_icon(raw: bytes) -> None:
    if len(raw) > MAX_ICON_BYTES:
        raise ValueError(f"icon is larger than {MAX_ICON_BYTES} bytes")
    if not raw.startswith(PNG_SIGNATURE) or raw[12:16] != b"IHDR" or len(raw) < 33:
        raise ValueError("icon is not a PNG")
    width, height = struct.unpack(">II", raw[16:24])
    low, high = ICON_PIXELS
    if width != height or not low <= width <= high:
        raise ValueError(f"icon must be a square PNG of {low} to {high} pixels, got {width}x{height}")


def plain_file(path: Path) -> bytes:
    if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"{path}: not a regular file")
    return path.read_bytes()


def collect(source: Path) -> dict[str, bytes]:
    entries = {"manifest.yml": f"schema: {SCHEMA}\n".encode()}
    packages = sorted(p for p in source.iterdir())
    if not packages:
        raise ValueError(f"{source} has no package directory")
    for directory in packages:
        if directory.is_symlink() or not directory.is_dir() or not PACKAGE.fullmatch(directory.name):
            raise ValueError(f"{directory}: expected a package directory named like com.example.app")
        files = {p.name: p for p in directory.iterdir()}
        extra = sorted(set(files) - {"metadata.yml", "icon.png"})
        if extra:
            raise ValueError(f"{directory}: unexpected file(s): {', '.join(extra)}")
        if "metadata.yml" not in files:
            raise ValueError(f"{directory}: metadata.yml is missing")
        metadata = plain_file(files["metadata.yml"])
        if len(metadata) > MAX_YAML_BYTES:
            raise ValueError(f"{files['metadata.yml']}: larger than {MAX_YAML_BYTES} bytes")
        try:
            check_metadata(metadata)
        except (ValueError, yaml.YAMLError) as error:
            raise ValueError(f"{files['metadata.yml']}: {error}") from error
        entries[f"metadata/{directory.name}/metadata.yml"] = metadata
        if "icon.png" in files:
            icon = plain_file(files["icon.png"])
            try:
                check_icon(icon)
            except ValueError as error:
                raise ValueError(f"{files['icon.png']}: {error}") from error
            entries[f"metadata/{directory.name}/en-US/icon.png"] = icon
    if len(entries) > MAX_ENTRIES:
        raise ValueError(f"more than {MAX_ENTRIES} archive entries")
    return entries


def write_archive(entries: dict[str, bytes], destination: Path) -> None:
    """Write a reproducible archive: sorted, fixed timestamps, no directory entries."""
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries, key=lambda n: (n != "manifest.yml", n)):
            info = zipfile.ZipInfo(name, EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, entries[name])
    if destination.stat().st_size > MAX_ARCHIVE_BYTES:
        destination.unlink()
        raise ValueError(f"{ARCHIVE} is larger than {MAX_ARCHIVE_BYTES} bytes")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} SOURCE_DIR OUTPUT_DIR", file=sys.stderr)
        return 2
    source, output = Path(argv[1]), Path(argv[2])
    if not source.is_dir():
        print(f"::notice::no {source} directory; not building {ARCHIVE}")
        return 0
    try:
        entries = collect(source)
    except (OSError, ValueError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    output.mkdir(parents=True, exist_ok=True)
    write_archive(entries, output / ARCHIVE)
    packages = sorted({n.split("/")[1] for n in entries if n.startswith("metadata/")})
    print(f"built {ARCHIVE} for {', '.join(packages)}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as handle:
            handle.write(f"path={output / ARCHIVE}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
