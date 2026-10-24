#!/usr/bin/env python3
"""Check the signed browser extension packages against the built source.

The Firefox XPI must carry a Mozilla signature, the Chromium CRX must be a CRX3
container, and both must contain exactly the built source files (the
manifest compared as JSON) at one and the same version.
"""
import argparse
import json
from pathlib import Path
import struct
import zipfile

IGNORED = {".amo-upload-uuid", ".web-extension-id"}


def verify(package, source):
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f"Corrupt extension archive: {package.name}")
        expected = {p.relative_to(source).as_posix(): p for p in source.rglob("*")
                    if p.is_file() and p.name not in IGNORED}
        actual = {n for n in archive.namelist()
                  if not n.endswith("/") and not n.startswith("META-INF/")}
        if set(expected) != actual:
            raise RuntimeError(f"Unexpected or missing files in {package.name}: "
                               f"{sorted(set(expected) ^ actual)}")
        for name, path in expected.items():
            a, b = archive.read(name), path.read_bytes()
            matches = json.loads(a) == json.loads(b) if name == "manifest.json" else a == b
            if not matches:
                raise RuntimeError(f"{package.name} differs from source: {name}")
        return json.loads(archive.read("manifest.json")), archive.namelist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firefox-source", type=Path, required=True)
    parser.add_argument("--chromium-source", type=Path, required=True)
    parser.add_argument("--firefox", type=Path, required=True, help="signed XPI")
    parser.add_argument("--chromium", type=Path, required=True, help="signed CRX")
    args = parser.parse_args()

    firefox_manifest, entries = verify(args.firefox, args.firefox_source)
    chromium_manifest, _ = verify(args.chromium, args.chromium_source)
    if firefox_manifest["version"] != chromium_manifest["version"]:
        raise RuntimeError("Firefox and Chromium versions differ")
    if not any(n.startswith("META-INF/") and n.endswith((".rsa", "cose.sig")) for n in entries):
        raise RuntimeError("Missing Mozilla signature")
    with args.chromium.open("rb") as stream:
        magic, crx_version, header_size = struct.unpack("<4sII", stream.read(12))
        stream.seek(12 + header_size)
        if magic != b"Cr24" or crx_version != 3 or stream.read(4) != b"PK\x03\x04":
            raise RuntimeError("Chromium package is not a CRX3 signed container")
    print(f"Signed packages match the extension source (version {firefox_manifest['version']})")


if __name__ == "__main__":
    main()
