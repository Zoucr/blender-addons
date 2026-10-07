"""Small, animated guide-following light rig for Eevee.

Actual light objects are used because an emission shader on thin strands is
not a dependable source of direct lighting in Eevee. Drivers and Follow Path
constraints make the rig update in both viewport and final-frame renders.
"""
import bpy

MAX_LIGHTS = 8
LIGHT_TAG = 'sf_guide_light'


def valid_guides(system):
    return [(row.obj, row.reverse) for row in system.sf.guides
            if row.enabled and row.obj and row.obj.type == 'CURVE'
            and any(len(sp.bezier_points if sp.type == 'BEZIER' else sp.points) >= 2
                    for sp in row.obj.data.splines)]


def controlled_lights(system):
    group = system.sf.light_rig
    if not group:
        return []
    return [obj for obj in group.objects if obj.type == 'LIGHT' and obj.get(LIGHT_TAG)]


def driver(node, property_name, system, expression, names):
    fcurve = node.driver_add(property_name)
    d = fcurve.driver
    d.type = 'SCRIPTED'
    for name in names:
        var = d.variables.new()
        var.name = name
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'OBJECT'
        var.targets[0].id = system
        var.targets[0].data_path = 'sf.light_' + name
    d.expression = expression


def sync_appearance(system):
    s = system.sf
    for light in controlled_lights(system):
        light.data.color = s.light_color
        light.data.shadow_soft_size = s.light_radius


def remove(system):
    group = system.sf.light_rig
    if not group:
        return
    for light in controlled_lights(system):
        data = light.data
        bpy.data.objects.remove(light, do_unlink=True)
        if data.users == 0:
            bpy.data.lights.remove(data)
    system.sf.light_rig = None
    if not group.objects and not group.children and group.users <= 1:
        bpy.data.collections.remove(group)


def rebuild(system, scene):
    guides = valid_guides(system)
    remove(system)
    if not system.sf.light_enabled or not guides or scene is None:
        return 0
    group = bpy.data.collections.new(system.name + ' / Strand Flow Lights')
    scene.collection.children.link(group)
    system.sf.light_rig = group
    for index in range(MAX_LIGHTS):
        guide, reverse = guides[index % len(guides)]
        if hasattr(guide.data, 'use_path'):
            guide.data.use_path = True
        data = bpy.data.lights.new(f'{system.name} / Guide Light {index + 1}', 'POINT')
        light = bpy.data.objects.new(data.name, data)
        group.objects.link(light)
        light[LIGHT_TAG] = True
        light.location = (0, 0, 0)
        light.data.color = system.sf.light_color
        light.data.shadow_soft_size = system.sf.light_radius
        path = light.constraints.new('FOLLOW_PATH')
        path.name = 'Strand Flow Guide'
        path.target = guide
        path.use_fixed_location = True
        path.use_curve_follow = False
        fraction = f'min(1, ({index} + 0.5) / max(count, 1))'
        position = f'start + (end - start) * {fraction}'
        if reverse:
            position = '1 - (' + position + ')'
        driver(path, 'offset_factor', system, position, ('start', 'end', 'count'))
        driver(data, 'energy', system,
               f'enabled * ({index} < count) * power / max(count, 1)',
               ('enabled', 'count', 'power'))
    return MAX_LIGHTS


class SF_OT_refresh_lights(bpy.types.Operator):
    bl_idname = 'sf.refresh_lights'
    bl_label = 'Refresh Guide Lights'
    bl_description = 'Rebuild the small light rig after changing guide objects or their direction'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from . import current_system
        system = current_system(context)
        if system is None:
            return {'CANCELLED'}
        count = rebuild(system, context.scene)
        if system.sf.light_enabled and not count:
            self.report({'WARNING'}, 'No usable guide curves for lights')
        return {'FINISHED'}


CLASSES = (SF_OT_refresh_lights,)
