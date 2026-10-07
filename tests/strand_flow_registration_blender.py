"""Exercise extension registration under Blender's restricted add-on context."""
import sys
from pathlib import Path

import bpy
from bpy_restrict_state import RestrictBlend

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons'))
import strand_flow

# Blender restricts bpy.data while enabling extensions. The startup scan must
# happen only after this context has ended.
with RestrictBlend():
    strand_flow.register()

mesh = bpy.data.meshes.new('Existing Strand Flow Geometry')
system = bpy.data.objects.new('Existing Strand Flow', mesh)
bpy.context.scene.collection.objects.link(system)
system.sf.is_system = True
system.sf.engine = 'GN'
strand_flow._PENDING.clear()
strand_flow.tick()
assert system.name in strand_flow._PENDING

strand_flow.unregister()
print('RESTRICTED_REGISTRATION_TEST_PASS')
