# Camera Path Rig 1.9.0 import

Source: user-supplied `Camera_Path_Rig_1.9.0.zip`.

Original archive SHA-256:
`a4d67e794192c7a477a8cdb4456c2e60b2329e94017b6ad6f4e75b10a29992a7`

All nine files are imported byte-for-byte under `addons/camera_path_rig/`.
The existing extension ID, version, author, GPL-3.0-or-later license and upstream
attribution remain unchanged. The archive already has an extension manifest;
no migration or code changes were required. Blender's packaging tool rebuilds
the download ZIP with the manifest at its root.

The original archive remains in the user's uploaded files. The repository
tracks editable source instead of an additional copy of the binary archive.

Validation: Blender 4.5.3 package build, manifest/archive validation and repository
catalog generation passed. All nine imported files match the source archive
byte-for-byte. The user confirmed that the add-on already works in Blender.
No further runtime testing or behavior changes are part of this import.
The supplied manifest declares Blender 4.2+; that compatibility declaration is
preserved, not independently verified across every version.

For an existing disk installation, save your work and note custom add-on
preferences first. Disable the old installation before enabling the repository
copy, since they register the same Blender operators. The extension module name
depends on its repository, so preferences may need to be re-entered when moving
between repositories. Existing rig data/property names are unchanged.
