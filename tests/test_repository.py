import importlib.util
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("builder", Path(__file__).resolve().parents[1] / "scripts/build_repository.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "addons"
        self.source.mkdir()
        self.output = self.root / "site"

    def package(self, addon_id="demo"):
        folder = self.source / "demo"
        folder.mkdir()
        (folder / "blender_manifest.toml").write_text(f'id = "{addon_id}"\ntype = "add-on"\nversion = "1.0.0"\n')
        (folder / "__init__.py").write_text('def register(): pass\ndef unregister(): pass\n')
        return folder

    def test_empty_feed(self):
        with patch.object(builder.subprocess, "run") as run:
            builder.build(self.source, self.output, "not-installed")
            run.assert_not_called()
        index = json.loads((self.output / "index.json").read_text())
        self.assertEqual(index, {"version": "v1", "blocklist": [], "data": []})
        self.assertIn("No add-ons published", (self.output / "index.html").read_text())

    def test_id_mismatch_rejected(self):
        self.package("different")
        with self.assertRaises(ValueError):
            builder.discover(self.source)

    def test_missing_manifest_rejected(self):
        (self.source / "unfinished").mkdir()
        with self.assertRaises(ValueError):
            builder.discover(self.source)

    def test_invalid_python_rejected(self):
        (self.package() / "__init__.py").write_text("def broken(")
        with self.assertRaises(SyntaxError):
            builder.discover(self.source)

    def test_existing_output_preserved(self):
        self.output.mkdir()
        marker = self.output / "keep.txt"
        marker.write_text("keep")
        with self.assertRaises(ValueError):
            builder.build(self.source, self.output, "blender")
        self.assertEqual(marker.read_text(), "keep")

    def test_valid_package_discovered(self):
        self.package()
        self.assertEqual(len(builder.discover(self.source)), 1)

    def test_symlink_rejected(self):
        folder = self.package()
        (folder / "external.py").symlink_to(self.root / "outside.py")
        with self.assertRaises(ValueError):
            builder.discover(self.source)

    @unittest.skipUnless(os.environ.get("BLENDER_EXTENSION_CLI"), "Optional official CLI integration test")
    def test_official_blender_packaging(self):
        folder = self.package()
        (folder / "blender_manifest.toml").write_text('''schema_version = "1.0.0"
id = "demo"
version = "1.0.0"
name = "Packaging Test"
tagline = "Verify extension repository packaging"
maintainer = "Test"
type = "add-on"
blender_version_min = "4.2.0"
license = ["SPDX:GPL-3.0-or-later"]
''')
        real_run = subprocess.run

        def official_cli(command, **kwargs):
            self.assertEqual(command[1:5], ["--background", "--factory-startup", "--command", "extension"])
            return real_run([sys.executable, os.environ["BLENDER_EXTENSION_CLI"], *command[5:]], **kwargs)

        with patch.object(builder.subprocess, "run", side_effect=official_cli):
            builder.build(self.source, self.output, "blender")
        index = json.loads((self.output / "index.json").read_text())
        self.assertEqual(index["data"][0]["id"], "demo")
        self.assertTrue(index["data"][0]["archive_hash"].startswith("sha256:"))
        self.assertTrue((self.output / index["data"][0]["archive_url"]).is_file())


if __name__ == "__main__":
    unittest.main()
