import bpy

from .ds_consts import CLEANUP_IDNAME, CLEANUP_LABEL, CLEANUP_PANEL_LABEL, CLEANUP_PANEL_IDNAME
from .ds_utils import vertex_group_from_outer_boundary, decimate_object

bl_info = {
    "name": "Cleanup Tool",
    "author": "Nico Breycha",
    "version": (0, 0, 2),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "A quick pass on cleaning the meshes geometry",
    "category": "Object",
}


class MESH_OT_clean_mesh(bpy.types.Operator):
    """Operator to clean selected mesh based on specified criteria."""
    bl_idname = CLEANUP_IDNAME
    bl_label = CLEANUP_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Gather Variables
        initial_reduction = context.scene.initial_reduction
        loose_threshold = context.scene.loose_threshold
        boundary_length = context.scene.boundary_length
        merge_threshold = context.scene.merge_threshold

        # Ensure we're in object mode
        obj = context.active_object
        if obj.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        orig_name = obj.name

        # Determine initial reduction
        start_vert_cnt = len(obj.data.vertices)
        start_tri_cnt = len(obj.data.polygons)

        # Set iteration count in relation to reduction percentage
        if start_tri_cnt > initial_reduction:
            perc_red = start_tri_cnt / initial_reduction

            iterations = 1

            if perc_red > 0.8:
                iterations = 25
            elif perc_red > 0.6:
                iterations = 15
            elif perc_red > 0.4:
                iterations = 10
            elif perc_red > 0.2:
                iterations = 5

            # Set Vertex Group for Border Retention
            vg_name = vertex_group_from_outer_boundary(obj)

            # Do the Reduction
            decimate_object(obj, perc_red, iterations=iterations, vg_name=vg_name)

        # Ensure we're dealing with a mesh
        if obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh")
            return {'CANCELLED'}

        # Prune loose meshes that are below the user defined threshold
        initial_objects = set(bpy.data.objects)

        bpy.ops.mesh.separate(type='LOOSE')
        new_objects = [o for o in bpy.data.objects if o not in initial_objects and o.type == 'MESH']

        bpy.context.view_layer.update()

        meshes_to_join = []
        for mesh in new_objects:
            if len(mesh.data.vertices) < loose_threshold:
                bpy.data.objects.remove(mesh, do_unlink=True)
            else:
                meshes_to_join.append(mesh)

        # Join Mesh back together
        if meshes_to_join:
            for mesh in meshes_to_join:
                mesh.select_set(True)
                context.view_layer.objects.active = mesh  # Set last in list as active

            # Join the selected meshes
            bpy.ops.object.join()

            # Now the active object is the joined mesh
            obj = context.active_object  # Update obj to the newly joined mesh
            obj.name = orig_name
            obj.data.name = orig_name

        # Fill potential holes under the user defined boundary_length
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.fill_holes(sides=boundary_length)

        # Additional Cleanup Operations
        bpy.ops.mesh.dissolve_degenerate()
        bpy.ops.mesh.remove_doubles(threshold=merge_threshold, use_unselected=True)
        bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')

        bpy.ops.object.mode_set(mode='OBJECT')
        obj = context.active_object

        # Report the changes
        final_vert_count = len(obj.data.vertices)

        self.report({'INFO'}, f"Mesh cleaning completed: Removed {start_vert_cnt - final_vert_count} vertices.")
        return {'FINISHED'}


class VIEW3D_PT_clean_mesh(bpy.types.Panel):
    """Panel to set parameters and execute mesh cleaning"""
    bl_label = CLEANUP_PANEL_LABEL
    bl_idname = CLEANUP_PANEL_IDNAME
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "initial_reduction")
        layout.prop(scene, "loose_threshold")
        layout.prop(scene, "boundary_length")
        layout.prop(scene, "merge_threshold")
        layout.operator(CLEANUP_IDNAME)


classes = (MESH_OT_clean_mesh, VIEW3D_PT_clean_mesh)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.types.Scene.initial_reduction = bpy.props.IntProperty(name="Initial Reduction", default=1000000)
    bpy.types.Scene.loose_threshold = bpy.props.IntProperty(name="Loose Component Vertex Thr", default=1000)
    bpy.types.Scene.boundary_length = bpy.props.IntProperty(name="Max Boundary Length", default=1000)
    bpy.types.Scene.merge_threshold = bpy.props.FloatProperty(name="Merge Threshold", default=0.000001)


def unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)

    if hasattr(bpy.types, "initial_reduction"):
        del bpy.types.Scene.initial_reduction
    if hasattr(bpy.types, "loose_threshold"):
        del bpy.types.Scene.loose_threshold
    if hasattr(bpy.types, "boundary_length"):
        del bpy.types.Scene.boundary_length
    if hasattr(bpy.types, "merge_threshold"):
        del bpy.types.Scene.merge_threshold


if __name__ == "__main__":
    register()
