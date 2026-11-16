"""Tests for the F-Droid metadata archive builder."""

import importlib.util
import io
import stat
import struct
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

BUILDER = Path(__file__).resolve().parents[1] / ".github" / "actions" / "fdroid-metadata" / "build.py"
spec = importlib.util.spec_from_file_location("fdroid_metadata_build", BUILDER)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

PKG = "dev.example.app"
METADATA = "name: Example\nsummary: Short\ndescription: |\n  Long\nlicense: MIT\ncategories: [Development]\n"


def png(size=512):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return build.PNG_SIGNATURE + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"")) + chunk(b"IEND", b"")


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "fdroid"
        self.output = self.root / "out"

    def package(self, name=PKG, metadata=METADATA, icon=None):
        directory = self.source / name
        directory.mkdir(parents=True)
        (directory / "metadata.yml").write_text(metadata)
        if icon is not None:
            (directory / "icon.png").write_bytes(icon)
        return directory

    def run_builder(self):
        return build.main(["build.py", str(self.source), str(self.output)])

    def test_builds_the_documented_layout(self):
        self.package(icon=png())
        self.assertEqual(self.run_builder(), 0)
        with zipfile.ZipFile(self.output / build.ARCHIVE) as archive:
            self.assertEqual(archive.namelist(), [
                "manifest.yml", f"metadata/{PKG}/en-US/icon.png", f"metadata/{PKG}/metadata.yml"])
            self.assertEqual(archive.read("manifest.yml"), b"schema: 1\n")
            for info in archive.infolist():
                self.assertEqual(stat.S_IFMT(info.external_attr >> 16), stat.S_IFREG)

    def test_archive_is_reproducible(self):
        self.package(icon=png())
        self.run_builder()
        first = (self.output / build.ARCHIVE).read_bytes()
        (self.output / build.ARCHIVE).unlink()
        self.run_builder()
        self.assertEqual((self.output / build.ARCHIVE).read_bytes(), first)

    def test_missing_directory_is_not_an_error_and_builds_nothing(self):
        self.assertEqual(self.run_builder(), 0)
        self.assertFalse(self.output.exists())

    def test_invalid_sources_fail_the_build(self):
        cases = {
            "unknown field": {"metadata": METADATA + "signer: abc\n"},
            "bad license": {"metadata": "license: not valid!\n"},
            "bad category": {"metadata": "categories: [Nope]\n"},
            "long summary": {"metadata": "summary: " + "a" * 81 + "\n"},
            "yaml tag": {"metadata": "!!python/object/apply:os.system [id]\n"},
            "not a png": {"icon": b"<svg/>"},
            "tiny icon": {"icon": png(16)},
            "bad package name": {"name": "Not A Package"},
        }
        for label, arguments in cases.items():
            with self.subTest(label):
                with tempfile.TemporaryDirectory() as temp:
                    self.source = Path(temp) / "fdroid"
                    self.output = Path(temp) / "out"
                    self.package(**arguments)
                    self.assertEqual(self.run_builder(), 1)
                    self.assertFalse((self.output / build.ARCHIVE).exists())

    def test_unexpected_files_and_symlinks_fail_the_build(self):
        directory = self.package()
        (directory / "build.sh").write_text("x")
        self.assertEqual(self.run_builder(), 1)
        (directory / "build.sh").unlink()
        (directory / "icon.png").symlink_to("/etc/passwd")
        self.assertEqual(self.run_builder(), 1)


if __name__ == "__main__":
    unittest.main()
