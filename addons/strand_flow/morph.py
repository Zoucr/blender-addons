"""Paired guide morphing, preview and native per-frame mesh baking."""
import bpy
from mathutils import Vector
from bpy.app.handlers import persistent

BAKING = False


def is_rendering():
    return bpy.app.is_job_running('RENDER')


def blend_paths(paths_a, paths_b, factor, label='Guide'):
    if len(paths_a) != len(paths_b):
        raise ValueError(f'{label}: A and B need the same number of splines')
    result = []
    for index, (a, b) in enumerate(zip(paths_a, paths_b),1):
        if a is None and b is None: continue
        if a is None or b is None:
            raise ValueError(f'{label}: spline {index} is a stray point in only one set; repair that pair')
        if len(a) != len(b):
            raise ValueError('Internal sampling mismatch')
        result.append([pa.lerp(pb, factor) for pa, pb in zip(a, b)])
    return result


def sample_object(obj, inverse, count, reverse, depsgraph, evaluate, resample):
    if obj.type != 'CURVE':
        raise ValueError(f'{obj.name}: use a Bezier or Poly curve')
    if obj.mode == 'EDIT': obj.update_from_editmode()
    evaluated = obj.evaluated_get(depsgraph)
    matrix = inverse @ evaluated.matrix_world
    # to_curve applies shape keys and spline-enabled deformation when requested.
    data = obj.to_curve(depsgraph, apply_modifiers=True) if evaluate else obj.data
    paths = []
    try:
        for spline in data.splines:
            if spline.use_cyclic_u:
                raise ValueError(f'{obj.name}: guides must be open')
            poly = []
            if spline.type == 'BEZIER':
                points = spline.bezier_points
                if len(points) < 2:
                    paths.append(None); continue
                for a, b in zip(points, points[1:]):
                    for k in range(24):
                        t = k / 24; u = 1 - t
                        poly.append(matrix @ (u**3*a.co + 3*u*u*t*a.handle_right +
                                               3*u*t*t*b.handle_left + t**3*b.co))
                poly.append(matrix @ points[-1].co)
            elif spline.type == 'POLY':
                poly = [matrix @ Vector(p.co[:3]) for p in spline.points]
                if len(poly) < 2:
                    paths.append(None); continue
            else:
                raise ValueError(f'{obj.name}: use Bezier or Poly splines, not NURBS')
            if reverse: poly.reverse()
            paths.append(resample(poly, count))

        return paths
    finally:
        if evaluate: obj.to_curve_clear()


@persistent
def preview_frame(scene, depsgraph=None):
    from . import generate, _BUSY
    if BAKING or _BUSY or is_rendering() or depsgraph is None: return
    for obj in scene.objects:
        if obj.type != 'MESH' or obj.sf.engine=='GN' or not obj.sf.is_system or not obj.sf.morph_preview: continue
        if obj.sf.bake_collection: continue
        try: generate(obj, False, depsgraph)
        except Exception as exc: obj.sf.status = str(exc)


class SF_OT_duplicate_b(bpy.types.Operator):
    bl_idname = 'sf.duplicate_b'
    bl_label = 'Duplicate A to B'
    bl_description = 'Create independent B copies for rows without a target; existing B curves are kept'
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        from . import current_system, dirty
        obj = current_system(context)
        if not obj or context.mode != 'OBJECT': return {'CANCELLED'}
        made = 0
        for entry in obj.sf.guides:
            if not entry.obj or entry.target: continue
            target = entry.obj.copy(); target.data = entry.obj.data.copy()
            target.name = entry.obj.name + ' B'
            # The B copy is independent rather than driven by the A action.
            target.animation_data_clear()
            target.data.animation_data_clear()
            if target.data.shape_keys: target.data.shape_keys.animation_data_clear()
            context.collection.objects.link(target)
            entry.target = target; entry.reverse_b = entry.reverse
            made += 1
        obj.sf.morph_preview = True
        dirty(obj.sf, context)
        self.report({'INFO'}, f'Created {made} B guides; select B in a guide row to edit')
        return {'FINISHED'}


class SF_OT_select_target(bpy.types.Operator):
    bl_idname = 'sf.select_target'; bl_label = 'Select Guide B'
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        from . import current_system
        obj = current_system(context)
        if not obj or context.mode != 'OBJECT': return {'CANCELLED'}
        s = obj.sf
        if not 0 <= s.active_guide < len(s.guides): return {'CANCELLED'}
        target = s.guides[s.active_guide].target
        if not target or target.name not in context.view_layer.objects:
            self.report({'ERROR'}, 'Assign a B guide in the current view layer'); return {'CANCELLED'}
        context.scene.sf_system = obj
        for item in context.selected_objects: item.select_set(False)
        target.hide_set(False); target.select_set(True)
        context.view_layer.objects.active = target
        return {'FINISHED'}


def remove_sequence(collection):
    # Only used for this operator's newly created sequence or explicitly stored bake.
    for obj in list(collection.objects):
        if not obj.get('sf_baked_frame', False): continue
        mesh = obj.data if obj.type == 'MESH' else None
        action = obj.animation_data.action if obj.animation_data else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh and mesh.users == 0: bpy.data.meshes.remove(mesh)
        if action and action.users == 0: bpy.data.actions.remove(action)
    if not collection.objects and not collection.children:
        bpy.data.collections.remove(collection)


def snapshot(system, collection, frame, context):
    from . import generate
    depsgraph = context.evaluated_depsgraph_get()
    generate(system, True, depsgraph)
    obj = bpy.data.objects.new(f'{system.name} / {frame:05d}', system.data.copy())
    collection.objects.link(obj)
    obj['sf_baked_frame'] = True
    obj.matrix_world = system.evaluated_get(depsgraph).matrix_world.copy()
    # Blender-native visibility keys: no render handler, add-on or external cache needed.
    for f, hidden in ((frame-1, True), (frame, False), (frame+1, True)):
        obj.hide_render = hidden; obj.hide_viewport = hidden
        obj.keyframe_insert('hide_render', frame=f)
        obj.keyframe_insert('hide_viewport', frame=f)
    obj.hide_render = False; obj.hide_viewport = False
    return obj


class SF_OT_bake_morph(bpy.types.Operator):
    bl_idname = 'sf.bake_morph'; bl_label = 'Bake Animation'
    bl_description = 'Bake full-density meshes for each integer frame; ESC cancels, save the blend afterwards'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global BAKING
        from . import current_system, _PENDING, read_guides
        system = current_system(context)
        if not system or context.mode != 'OBJECT' or BAKING: return {'CANCELLED'}
        s = system.sf
        if s.engine=='GN':
            self.report({'INFO'},'V4 evaluates directly during rendering; no bake needed'); return {'CANCELLED'}
        if s.bake_collection:
            self.report({'ERROR'}, 'Clear the existing bake before baking again'); return {'CANCELLED'}
        frames = s.bake_end - s.bake_start + 1
        if frames < 1:
            self.report({'ERROR'}, 'End must be at or after Start'); return {'CANCELLED'}
        estimate = frames * s.count * s.points * (s.sides if s.shape == 'TUBE' else 2)
        if estimate > 12000000 or frames > 1000:
            self.report({'ERROR'}, 'Bake too large: reduce frame range, strands, points or sides (12M vertices / 1000 frames limit)')
            return {'CANCELLED'}
        try: read_guides(system)
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        self.system = system; self.scene = context.scene
        self.original_frame = self.scene.frame_current
        self.original_subframe = self.scene.frame_subframe
        self.live = s.live; self.preview = s.morph_preview
        self.original_mesh = system.data.copy()
        self.start = s.bake_start; self.end = s.bake_end; self.frame = self.start
        self.collection = bpy.data.collections.new(system.name + ' / Baked Animation')
        self.scene.collection.children.link(self.collection)
        BAKING = True
        _PENDING.pop(system.name, None)
        s.live = False; s.morph_preview = False
        context.window_manager.progress_begin(self.start, self.end + 1)
        self.timer = None
        if bpy.app.background:
            try:
                while self.frame <= self.end:
                    self.scene.frame_set(self.frame)
                    context.view_layer.update()
                    snapshot(self.system, self.collection, self.frame, context)
                    self.frame += 1
                self.finish(context, True)
                return {'FINISHED'}
            except Exception as exc:
                self.finish(context, False)
                self.report({'ERROR'}, f'Bake cancelled: {exc}')
                return {'CANCELLED'}
        self.timer = context.window_manager.event_timer_add(.05, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC':
            self.finish(context, False); return {'CANCELLED'}
        if event.type != 'TIMER' or event.timer != self.timer: return {'RUNNING_MODAL'}
        try:
            self.scene.frame_set(self.frame)
            context.view_layer.update()
            snapshot(self.system, self.collection, self.frame, context)
            context.window_manager.progress_update(self.frame + 1)
            self.system.sf.status = f'Baking {self.frame}/{self.end} (Esc cancels)'
            self.frame += 1
            if self.frame > self.end:
                self.finish(context, True); return {'FINISHED'}
        except Exception as exc:
            self.finish(context, False)
            self.report({'ERROR'}, f'Bake cancelled: {exc}')
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        if BAKING: self.finish(context, False)

    def finish(self, context, success):
        global BAKING
        from . import _PENDING
        if self.timer: context.window_manager.event_timer_remove(self.timer)
        context.window_manager.progress_end()
        s = self.system.sf
        try:
            current = self.system.data
            self.system.data = self.original_mesh
            if current.users == 0: bpy.data.meshes.remove(current)
            if success:
                s.bake_collection = self.collection
                s.bake_old_hide_render = self.system.hide_render
                s.bake_old_hide_viewport = self.system.hide_get()
                self.system.hide_render = True; self.system.hide_set(True)
                context.scene.sf_system = self.system
                s.status = f'Baked {self.end-self.start+1} frames. Save the .blend'
            else:
                remove_sequence(self.collection)
                s.live = self.live; s.morph_preview = self.preview
                s.status = 'Bake cancelled; original output restored'
            _PENDING.pop(self.system.name, None)
            self.scene.frame_set(self.original_frame, subframe=self.original_subframe)
            context.view_layer.update()
        finally:
            BAKING = False


class SF_OT_clear_bake(bpy.types.Operator):
    bl_idname = 'sf.clear_bake'; bl_label = 'Clear Bake / Resume Editing'
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        from . import current_system
        system = current_system(context)
        if not system or not system.sf.bake_collection or BAKING: return {'CANCELLED'}
        s = system.sf; collection = s.bake_collection
        # Duplicated systems can share the pointer. Avoid destroying another system's bake.
        if any(o != system and o.type == 'MESH' and o.sf.bake_collection == collection for o in bpy.data.objects):
            self.report({'ERROR'}, 'Another system shares this bake; unlink its Bake Collection first')
            return {'CANCELLED'}
        s.bake_collection = None
        remove_sequence(collection)
        system.hide_render = s.bake_old_hide_render
        system.hide_set(s.bake_old_hide_viewport)
        s.morph_preview = True; s.status = 'Bake cleared; preview enabled'
        return {'FINISHED'}


class SF_PT_morph(bpy.types.Panel):
    bl_label = 'Guide Animation'; bl_idname = 'SF_PT_morph'
    bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = 'Strand Flow'
    bl_parent_id = 'SF_PT_main'
    @classmethod
    def poll(cls, context):
        from . import current_system
        return current_system(context) is not None
    def draw(self, context):
        from . import current_system
        s = current_system(context).sf; l = self.layout
        if s.bake_collection:
            l.label(text='Baked output active. Clear to edit.', icon='CHECKMARK')
            l.operator('sf.clear_bake')
            return
        l.use_property_decorate = True
        if s.engine!='GN':l.prop(s, 'guide_animation', expand=True)
        if s.engine!='GN' and s.guide_animation=='MORPH':
            l.prop(s, 'blend', slider=True)
        else:
            l.prop(s,'wake_amount',slider=True)
            l.prop(s,'wake_spread')
            row=l.row(align=True);row.prop(s,'wake_start');row.prop(s,'wake_end')
            row=l.row(align=True);row.prop(s,'wake_fade_in');row.prop(s,'wake_fade_out')
            l.prop(s,'wake_noise');l.prop(s,'wake_frequency');l.prop(s,'wake_phase')
            if s.wake_end<=s.wake_start:l.label(text='End must be greater than Start',icon='ERROR')
            l.label(text='Outward from each group centre. Keyframe Amount.')
        if s.engine!='GN': l.prop(s, 'morph_preview')
        if s.engine!='GN' and s.guide_animation=='MORPH':
            l.operator('sf.duplicate_b')
            l.label(text='Pair A and B in Guides. Missing B keeps A.')
        elif s.engine!='GN':
            l.label(text='Uses one guide set.')
        if s.engine=='GN':
            l.label(text='Guide deformation evaluates automatically.')
            l.label(text='Render animation directly; no bake required.')
            return
        l.prop(s, 'evaluated_guides')
        box = l.box(); box.label(text='Final animation')
        row = box.row(align=True); row.prop(s, 'bake_start'); row.prop(s, 'bake_end')
        box.operator('sf.bake_morph')
        box.label(text='Bake before rendering; save the .blend.')


CLASSES = (SF_OT_duplicate_b, SF_OT_select_target, SF_OT_bake_morph,
           SF_OT_clear_bake, SF_PT_morph)
