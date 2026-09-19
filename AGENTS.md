# Add-on repository rules

- Preserve unrelated work. Use branches and PRs for future changes unless the
  user explicitly requests a direct publish. `main` is the public release source.
- Import user-supplied files from `incoming/` only when requested. Never execute
  imported scripts just to inspect them. Check archive paths before extraction.
- Keep one reviewed extension under `addons/<id>/`. Its manifest ID must match
  the directory and stay stable; use semantic versions and bump changed releases.
- Use Blender's extension format (`blender_manifest.toml` and `__init__.py`).
  Legacy conversion must review relative imports, `__package__`, preference IDs,
  data paths, handlers, registration/unregistration, dependencies and permissions.
- Preserve copyright and licenses; ask if redistribution rights are unclear.
  Do not publish third-party or private/client assets without permission.
- Do not check in build outputs, secrets, virtualenvs or downloaded model weights.
- Run infrastructure tests and package validation. Test actual Blender behavior
  when possible, and say exactly what could not be tested. Syntax alone is not
  runtime validation. Test against the add-on's declared Blender target.
- New versions must preserve settings or document a migration. Do not replace an
  existing add-on with a differently named variant merely to implement an update.
- If an incoming file is replaced by source, keep it until the user agrees to
  remove it. Never silently delete original submissions.
