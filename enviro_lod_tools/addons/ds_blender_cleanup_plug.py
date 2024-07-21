import bpy

from .ds_consts import CLEANUP_IDNAME, CLEANUP_LABEL, CLEANUP_PANEL_LABEL, CLEANUP_PANEL_IDNAME

bl_info = {
    "name": "Cleanup Tool",
    "author": "Nico Breycha",
    "version": (0, 0, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "A quick pass on cleaning the meshes geometry",
    "category": "Object",
}


class MESH_OT_clean_mesh(bpy.types.Operator):
    """Operator to clean selected mesh based on specified criteria and report changes"""
    bl_idname = CLEANUP_IDNAME
    bl_label = CLEANUP_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        poly_count = context.scene.poly_count
        boundary_length = context.scene.boundary_length
        iterations = context.scene.iterations  # TODO Unimplemented
        merge_threshold = context.scene.merge_threshold

        # Ensure we're in object mode
        obj = context.active_object
        if obj.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        start_vert_count = len(obj.data.vertices)

        # Ensure we're dealing with a mesh
        if obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh")
            return {'CANCELLED'}

        # Store initial list of mesh objects
        initial_objects = set(bpy.data.objects)

        # Separate mesh by loose parts
        bpy.ops.mesh.separate(type='LOOSE')

        new_objects = [o for o in bpy.data.objects if o not in initial_objects and o.type == 'MESH']

        bpy.context.view_layer.update()

        # Collect meshes that are not to be deleted
        meshes_to_join = []
        for mesh in new_objects:
            if len(mesh.data.vertices) < poly_count:
                bpy.data.objects.remove(mesh, do_unlink=True)
            else:
                meshes_to_join.append(mesh)

        # Select meshes to join
        if meshes_to_join:
            for mesh in meshes_to_join:
                mesh.select_set(True)
                context.view_layer.objects.active = mesh  # Set last in list as active

            # Join the selected meshes
            bpy.ops.object.join()

            # Now the active object is the joined mesh
            obj = context.active_object  # Update obj to the newly joined mesh

        # Fill holes
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.fill_holes(sides=boundary_length)

        # Dissolve Degens
        bpy.ops.mesh.dissolve_degenerate()

        # Merge by Dist
        bpy.ops.mesh.remove_doubles(threshold=merge_threshold, use_unselected=True)

        # Triangulate the model
        bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')

        bpy.ops.object.mode_set(mode='OBJECT')
        obj = context.active_object

        final_vert_count = len(obj.data.vertices)

        # Report the changes
        self.report({'INFO'}, f"Mesh cleaning completed: Removed {start_vert_count - final_vert_count} vertices.")
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

        layout.prop(scene, "poly_count")
        layout.prop(scene, "boundary_length")
        layout.prop(scene, "iterations")
        layout.prop(scene, "merge_threshold")
        layout.operator(CLEANUP_IDNAME)

classes = (MESH_OT_clean_mesh, VIEW3D_PT_clean_mesh)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.types.Scene.poly_count = bpy.props.IntProperty(name="Loose Component Vertex Thr", default=1000)
    bpy.types.Scene.boundary_length = bpy.props.IntProperty(name="Max Boundary Length", default=1000)
    bpy.types.Scene.iterations = bpy.props.IntProperty(name="Iterations", default=20)
    bpy.types.Scene.merge_threshold = bpy.props.FloatProperty(name="Merge Threshold", default=0.000001)


def unregister():
    from bpy.utils import unregister_class

    for cls in classes:
        unregister_class(cls)

    if hasattr(bpy.types, "poly_count"):
        del bpy.types.Scene.poly_count
    if hasattr(bpy.types, "boundary_length"):
        del bpy.types.Scene.boundary_length
    if hasattr(bpy.types, "iterations"):
        del bpy.types.Scene.iterations
    if hasattr(bpy.types, "merge_threshold"):
        del bpy.types.Scene.merge_threshold


if __name__ == "__main__":
    register()
