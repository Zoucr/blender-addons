"""Build a static extension repository using Blender's own packaging tools."""
import argparse
import ast
import html
import json
from pathlib import Path
import re
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def discover(source):
    packages = []
    if not source.is_dir():
        raise ValueError(f"Missing source directory: {source}")
    for folder in sorted(source.iterdir()):
        if folder.is_symlink():
            raise ValueError(f"Symlinks are not allowed in source: {folder}")
        if not folder.is_dir() or folder.name.startswith('.'):
            continue
        manifest = folder / "blender_manifest.toml"
        if not manifest.is_file():
            raise ValueError(f"Missing manifest: {folder}")
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        if data.get("id") != folder.name:
            raise ValueError(f"Folder name must match manifest id: {folder}")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", folder.name):
            raise ValueError(f"Invalid stable extension id: {folder.name}")
        if data.get("type") != "add-on" or not (folder / "__init__.py").is_file():
            raise ValueError(f"Expected an add-on with __init__.py: {folder}")
        for path in folder.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Symlinks are not allowed in packages: {path}")
            if path.suffix == ".py" and path.is_file():
                ast.parse(path.read_bytes(), filename=str(path))
        packages.append((folder, data))
    return packages


def build(source, output, blender):
    packages = discover(source)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output must be an absent or empty directory; refusing to overwrite")
    output.mkdir(parents=True, exist_ok=True)
    for folder, _ in packages:
        subprocess.run([blender, "--background", "--factory-startup", "--command",
                        "extension", "build", "--source-dir", str(folder.resolve()),
                        "--output-dir", str(output.resolve())], check=True)
    if packages:
        archives = sorted(output.glob("*.zip"))
        if len(archives) != len(packages):
            raise ValueError("Expected exactly one archive per extension")
        for archive in archives:
            subprocess.run([blender, "--background", "--factory-startup", "--command",
                            "extension", "validate", str(archive.resolve())], check=True)
        subprocess.run([blender, "--background", "--factory-startup", "--command",
                        "extension", "server-generate", "--repo-dir",
                        str(output.resolve())], check=True)
    else:
        (output / "index.json").write_text(json.dumps({
            "version": "v1", "blocklist": [], "data": []
        }, indent=2) + "\n", encoding="utf-8")
    index = json.loads((output / "index.json").read_text(encoding="utf-8"))
    if len(index["data"]) != len(packages):
        raise ValueError("Generated catalog does not match the source packages")
    rows = "".join(
        f'<li><a href="{html.escape(item["archive_url"], quote=True)}">'
        f'{html.escape(item["name"])} {html.escape(item["version"])}</a></li>'
        for item in index["data"]
    ) or "<li>No add-ons published yet.</li>"
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Lucca’s Blender add-ons</title><main>'
        '<h1>Lucca’s Blender add-ons</h1>'
        '<p>Add this URL as a remote repository in Blender:</p>'
        '<p><code>https://zoucr.github.io/blender-addons/index.json</code></p>'
        f'<ul>{rows}</ul>'
        '<p><a href="https://github.com/Zoucr/blender-addons">Source and instructions</a></p>'
        '</main></html>\n', encoding="utf-8")
    (output / ".nojekyll").touch()
    print(f"Built {len(packages)} extension(s) in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "addons")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--blender", default="blender")
    args = parser.parse_args()
    build(args.source, args.output, args.blender)
