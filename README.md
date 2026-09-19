# Lucca's Blender add-ons

One home for add-ons built with Codex, ChatGPT, or by hand. Source lives here;
GitHub Actions builds the installable ZIPs and a public Blender extension feed.

## Add-ons

| Add-on | Version | Location in Blender |
| --- | --- | --- |
| [Playblaster](addons/playblaster/README.md) | 1.0.0 | 3D View > N sidebar > Tool > Playblaster |
| [Camera Path Rig](addons/camera_path_rig/README.txt) | 1.9.0 | 3D View > N sidebar > Camera Path |

See [import notes and validation](docs/imports/camera_path_rig-1.9.0.md) for
compatibility and existing-installation guidance.

## Connect Blender (after the first successful Pages deployment)

In Preferences > Get Extensions, open the repository settings, add a Remote
Repository, and paste:

```text
https://zoucr.github.io/blender-addons/index.json
```

Allow online access when prompted. Refresh the repository to see published
extensions and available updates. Add-ons appear after their changes are merged
and the Pages deployment succeeds. A normal GitHub repository URL does not work here.

## One-time GitHub setup

Under Settings > Pages, select **GitHub Actions** as the build source.
Then open Actions > Publish Blender extensions > Run workflow on `main`.
The feed is live only after that workflow succeeds. All published code and ZIPs
are public; never include credentials, client material, or paid third-party code.

## Everyday workflow

| Starting point | What to do |
| --- | --- |
| New or updated add-on in Codex | Work inside `addons/<stable_id>/`, test, increase its manifest version, then publish by merging to `main`. |
| ZIP or Python file from ChatGPT in the browser | Upload it to `incoming/` with GitHub's Add file > Upload files, or attach it in Codex and ask to import it. |
| Existing local add-on | Same import route. Preserve its license, identity and settings where possible. |
| Already valid Blender extension | Unpack into `addons/<stable_id>/` with the manifest directly inside that folder, review and test before merging. |

Suggested request: "Import incoming/my_addon.zip, convert it to a Blender
extension, preserve existing settings, test what you can, and open a PR."

`incoming/` is a holding area, not a published feed. Uploads there do not publish
automatically. Old `bl_info` add-ons may need code changes, not just a manifest.
Imports, preferences identifiers, writable data paths and bundled dependencies
must be checked. Disable the old legacy installation when moving to an extension
to avoid duplicate registrations; back up settings first.

## Repository layout

- `addons/`: reviewed extension source, one folder per add-on.
- `incoming/`: files awaiting conversion/review (also publicly visible).
- `scripts/build_repository.py`: build, validate and generate the feed.
- `.github/workflows/publish.yml`: checks PRs and publishes pushes to `main`.
- `AGENTS.md`: conventions for Codex and other coding agents.

Each published folder needs `blender_manifest.toml`, `__init__.py`, a README and
the appropriate license file. Keep its ID and folder name stable across updates;
increase `version` for every published code change. Use `blender_version_min`
and, when needed, `blender_version_max` to state the tested compatibility range.
Declare permissions and package dependencies correctly. Do not bundle large
model downloads in this repository.

## Local checks

Python 3.11+ and Blender are required for building actual extensions:

```sh
python scripts/build_repository.py --blender /path/to/blender --output /path/to/new-output-folder
```

The output folder must be absent or empty. Run infrastructure tests with:

```sh
python -m unittest discover -s tests -v
```

CI uses Blender 4.5.3 for packaging, not as a claim that every add-on supports
4.5. Test each add-on's actual functionality in the Blender version it targets.
Package validation is not a runtime or security audit.

## Release safety

Use a branch and pull request for ongoing changes. Merging to `main` publishes
all folders in `addons/` automatically after checks pass. Incoming files and
tests are never included in the published site. A failed build does not replace
the existing site. For a fix or rollback, publish a new, higher add-on version;
Blender will not normally offer a lower version as an update.
