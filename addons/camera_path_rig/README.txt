Camera Path Rig 1.9.0
=====================

Purpose
-------
Camera Path Rig starts where a recorded-camera workflow normally ends. One
click creates an editable Bezier path, dolly, camera, aim control, focus
control, and start-to-end animation. It does not record viewport movement.

Install
-------
In Blender 4.2 or newer, open Edit > Preferences > Add-ons (or Extensions),
choose Install from Disk, and select Camera_Path_Rig_1.9.0.zip. Enable
"Camera Path Rig" if Blender does not enable it automatically.

Open the 3D Viewport sidebar with N and choose the "Camera Path" tab.

Workflow
--------
1. Put the 3D Cursor where the camera should aim.
2. Move the playhead to the frame where the new rig should start, choose a Path
   Preset, duration (frames or seconds), and camera lens.
3. Expand Creation > Rig Settings as needed, then press Generate Camera Path Rig.
4. Edit the Bezier curve directly in Blender when you want to reshape it. Use
   Path Controls > Smooth Path to reduce bumps; the endpoints stay fixed.
   Path Controls also exposes the camera Dolly's native 0-1 Progress field for
   direct keyframing along the main camera path.
   Line rigs start as three-point curves positioned behind the Cursor.
   The active path is drawn blue with repeated V-shaped chevrons showing its
   start-to-end travel direction. Show Direction toggles this overlay.
5. Move the red Aim control to point the camera. Move the green Focus control
   if the depth-of-field focus point should differ from the aim point.
6. Change a rig's timing and press Apply Timing. Expand Aim Path when the Aim
   should also travel smoothly: Create from Camera Path copies the current
   camera curve beside it and gives it an initially matching, independent
   Progress animation.
7. Use Make Camera Active for manual switching, or Add Camera Cut Here to bind
   the rig camera to a timeline marker at the current frame.
8. Use Bake Current Rig to New Camera for an unconstrained handoff camera. The
   baked camera receives transform, lens, and focus-distance keys every frame.

Using an existing Curve
-----------------------
1. Select the Curve object that should drive the new camera.
2. Under Creation > Rig Settings, set Path Preset to Selected Curve.
3. Choose the duration and lens, then generate the rig.

The source object and its Curve datablock remain untouched. A separate copy of
all splines and control points is placed in the new CameraPath_Rig_###
collection with the source's world transform. Render-only bevel/extrusion,
animation, parenting, and constraints are removed from the rig copy.

Path presets
------------
- Line: three editable points behind the 3D Cursor. Preset setting: Length.
- Half Circle: exact open 180-degree Bezier arc centred on the 3D Cursor.
  Preset setting: Radius.
- Full Circle: exact cyclic 360-degree Bezier orbit centred on the 3D Cursor.
  Preset setting: Radius.
- Selected Curve: duplicates the selected Curve into the rig.

Preset Settings is collapsed by default. The selected source name or missing
Curve warning remains visible for Selected Curve without opening another box.

Aim Path
--------
The collapsed Aim Path section sits between Path Controls and Camera Switching.
Create from Camera Path duplicates the camera curve and offsets the copy in
world space so its current progress point is underneath the current Aim. At the
camera rig's start this produces a parallel target path at the existing Aim
distance.

The Aim Dolly receives a separate copy of the camera dolly's progress keys at
creation time. Its Progress field can then be keyed and edited independently;
later Apply Timing operations on the camera path do not change it. Replace from
Camera Path updates only the curve geometry and keeps that independent timing.
Remove and Replace both preserve the Aim control's manual animation Action and
keyframes. While attached, those Aim keys remain available as local motion on
top of the Aim Dolly's path progress.

The main quick-select row always remains Curve, Aim, Focus, and Cam. When an Aim
Path exists, its panel adds a contextual Curve/Dolly selection row. Move Focus
with Aim Path makes Focus a sibling of Aim beneath the Aim Dolly. Disable it to
keep Focus independent in world space. Changing the option preserves Focus
animation and its current world transform; removing the Aim Path restores the
normal Focus-to-Aim hierarchy.

Multiple rigs
-------------
Rig numbering and discovery are local to each Blender scene. If Scene A contains
Rig 001 and Rig 002, its next rig is Rig 003 even when Scene B already contains
Rig 001 through Rig 004. Each scene receives separate master and bake
collections, and each generated rig carries a globally unique internal owner ID.

Existing cameras and earlier Camera Path Rigs are not reused or renamed. Select
a rig from the current scene's Existing Rig list to edit it. The highlighted row
is the current rig, a camera icon marks the active scene camera, and every row
shows that rig's start and end frames.

Delete Rig removes only the highlighted scene-local rig. Delete All removes all
Camera Path Rigs in the current scene, never rigs from another scene. Both
buttons open a confirmation dialog first. Cleanup includes camera-cut markers
made for deleted cameras and now-unused Curve, Mesh, Camera, and animation
Action datablocks. Shared data, unrelated orphan data, other scenes, and
independently baked cameras are preserved.

Timing detail
-------------
The displayed end frame is start frame + duration. At 24 fps, a duration of
5 seconds is 120 frame intervals, such as frame 1 through frame 121. Choose
Smooth Start/End for eased motion or Constant Speed for linear progress.

Viewport display preferences
----------------------------
Open Blender Preferences > Add-ons/Extensions > Camera Path Rig to adjust the
camera-path color, orange Aim Path color, line width, path opacity, arrow size,
and arrow count. The master Viewport Overlays switch in the 3D Viewport hides
both custom path displays along with Blender's other overlays.

Version 1.9.0
-------------
- Replaced the Existing Rig dropdown with a native scene-local scrolling list.
- The selected row is highlighted; rows show Rig number, start-end frames, and
  an icon when that rig's camera is the active scene camera.
- Added a split deletion row: Delete Rig on the left and red Delete All on the
  right. Both operations require confirmation before executing.
- Delete All is strictly limited to Camera Path Rigs in the current scene and
  uses the same ownership-scoped datablock cleanup as single-rig deletion.
- Added regression coverage for list-index selection and deleting all rigs in
  one scene while preserving rigs in two other scenes.

Version 1.8.0
-------------
- Rig discovery, the Existing Rig dropdown, and Rig 001/002/003 numbering are
  now scoped to the active Blender scene.
- Each scene receives its own Camera Path Rigs master collection and Camera Path
  Bakes collection instead of sharing global collections across scenes.
- New rigs carry both a scene owner ID and globally unique internal rig ID, so
  identical visible rig numbers in different scenes cannot collide.
- Rig control lookup and Delete This Rig are additionally bounded to the
  selected rig's own collection, protecting same-numbered legacy rigs as well.
- Added a two-scene regression covering independent numbering and verifying
  that deleting Scene A's Rig 001 leaves every Scene B Rig 001 object intact.

Version 1.7.2
-------------
- Added the main camera Dolly's native 0-1 Progress field and keyframe diamond
  to Path Controls, matching the Aim Path Progress workflow.
- The field edits the existing Follow Path animation directly, so no duplicate
  timing system or additional controller is created.

Version 1.7.1
-------------
- Moved Aim Path and Aim Dolly quick selection into the collapsed Aim Path
  panel. The main selection bar is always Curve, Aim, Focus, and Cam.
- Aim remains independently keyframeable as a child of the Aim Dolly, so its
  local keys can be layered over the Dolly's independently keyed 0-1 Progress.
- Added Move Focus with Aim Path. Enabled parents Focus to the Aim Dolly;
  disabled keeps it independent in world space.
- Focus parenting changes preserve its current world transform, Action, and
  keyframes. Removing the Aim Path restores Focus beneath Aim.

Version 1.7.0
-------------
- Replaced the Aim/Focus transform fields in the old Animation section with a
  compact, collapsed Aim Path workflow.
- Create from Camera Path duplicates the current camera curve and positions it
  as a parallel path through the current Aim location.
- The new Aim Dolly starts with a copy of the camera progress keys, then remains
  independently keyframeable through its Progress field.
- Replace updates Aim Path geometry without resetting its timing. Replace and
  Remove preserve all manual Aim keyframes.
- Active Aim Paths receive orange direction arrows and a conditional Aim Path
  quick-select button. Camera and Aim Path colors are separately configurable
  in add-on Preferences.
- Whole-rig deletion also cleans the owned Aim Path, Aim Dolly, curve data, and
  independent progress Action.

Version 1.6.3
-------------
- Scene-based UI initialization now waits until Blender has left its restricted
  extension-registration context, avoiding the `_RestrictData.scenes` error.
- Normal script registration and file-load initialization remain immediate.

Version 1.6.2
-------------
- Registration is now idempotent and recovers from stale Camera Path Rig
  classes left in memory after an in-place Blender extension update.
- Partial enable/disable attempts are cleaned defensively without unregistering
  classes belonging to unrelated add-ons.

Version 1.6.1
-------------
- Delete This Rig now removes the selected rig's zero-user Curve, Mesh, Camera,
  and animation Action datablocks instead of leaving them behind.
- Cleanup is ownership-scoped and never runs a global orphan purge. Shared
  datablocks, unrelated unused data, other rigs, and baked cameras stay intact.
- New rig-created data carries an owner tag, with a conservative exclusive-user
  fallback so rigs created by earlier versions can also be cleaned safely.

Version 1.6.0
-------------
- Renamed the Straight preset to Line.
- Removed the "Starts at current frame" text from Creation; new rigs still
  start at the current playhead frame.
- Creation, Rig Settings, Preset Settings, Timing, Path Controls, Animation,
  and Camera Switching now default to collapsed. Pre-1.6 scenes receive this
  tidy layout once when loaded, and generating a rig collapses the sections
  again for a clean handoff to the new rig.
- Split the add-on into focused common, overlay, properties, operators, and UI
  modules with a small registration-only package entry point.

Version 1.5.0
-------------
- Path Preset dropdown: Line, Half Circle, Full Circle, Selected Curve.
- Closed-by-default, context-sensitive Preset Settings for Length or Radius.
- Exact editable Bezier arcs centred on the 3D Cursor for circular presets.
- Compact Animation section with live native Location/Rotation fields and
  keyframe diamonds for both Aim and Focus, independent of object selection.
- Cyclic-aware path smoothing and closed direction overlay for Full Circle.

Version 1.4.0
-------------
- Creation can use either the standard starter curve or the selected Curve.
- Selected curves are duplicated into the new rig; the original stays intact.
- The copied path retains its splines, control points, and world transform.
- Rig control sizes adapt to the dimensions of the copied curve.

Version 1.3.1
-------------
- Starter and smoothed paths now use Aligned handles instead of automatic
  handles, so their direction can be rotated manually in Edit Mode.
- Selecting Curve converts automatic handles on older generated rigs to
  rotatable Aligned handles without changing their current shape.

Version 1.3.0
-------------
- New rigs begin at the current timeline frame; Creation only asks for duration.
- Aim and Focus start at the 3D Cursor.
- Starter path is a straight three-point Bezier curve behind the Cursor.
- Overlay color, width, opacity, arrow size, and arrow count preferences.
- Blue path overlay now respects Blender's master Viewport Overlays toggle.
- Curve added to the Aim / Focus / Cam quick-select row.

Version 1.2.0
-------------
- Blue active-path overlay with repeated direction chevrons.
- Show Direction toggle under Path Controls.

Version 1.1.0
-------------
- Collapsible Creation and Rig Settings sections.
- Collapsible Timing, Path Controls, and Camera Switching sections.
- Simplified Path Controls with an endpoint-preserving smoothing amount.
- Per-frame bake to a new independent camera for reliable handoff.

License and attribution
-----------------------
GPL-3.0-or-later.

The rig concept is informed by AutoCam Free by RenderRides, supplied under
GPL-3.0-or-later. This add-on is a focused, independently implemented tool for
generating camera rigs and starter curves without the recording stage.
