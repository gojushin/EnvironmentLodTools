import ensurepip

import bpy

from .ds_consts import CLEANUP_IDNAME, CLEANUP_LABEL, CLEANUP_PANEL_LABEL, CLEANUP_PANEL_IDNAME, PYFQMR_MODULE_NAME
from .ds_utils import (decimate_with_pyqmfr, keep_largest_component, clean_mesh_geometry,
                       ensure_package_installed, uninstall_package, resolve_bmesh)

ENV_IS_BLENDER = bpy.app.binary_path != ""

bl_info = {
    "name": "Cleanup Tool",
    "author": "Nico Breycha",
    "version": (0, 0, 3),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "A quick pass on cleaning the meshes geometry",
    "category": "Object",
}


class MESH_OT_clean_mesh(bpy.types.Operator):
    """Operator to clean selected mesh based on specified criteria."""
    bl_idname = CLEANUP_IDNAME
    bl_label = CLEANUP_LABEL
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Gather Variables
        initial_reduction = context.scene.initial_reduction
        loose_threshold = context.scene.loose_threshold
        boundary_length = context.scene.boundary_length
        merge_threshold = context.scene.merge_threshold

        # Ensure we're dealing with a mesh
        obj = context.active_object
        orig_name = obj.name

        if obj.type != "MESH":
            self.report({"ERROR"}, f"Active object {orig_name} is not a mesh")
            return {"CANCELLED"}

        bm = keep_largest_component(obj, return_bm=True) # TODO add loose threshold
        bm = clean_mesh_geometry(obj, merge_threshold, bm=bm, return_bm=True)

        # Determine initial reduction
        start_vert_cnt = len(bm.verts)
        start_tri_cnt = len(bm.faces)

        print("Starting iterative mesh reduction...")
        # Set iteration count in relation to reduction percentage
        if start_tri_cnt > initial_reduction:
            # Do the Reduction
            try:
                bm = decimate_with_pyqmfr(obj, initial_reduction, bm=bm, max_iterations=100, preserve_border=True,
                                          merge_threshold=merge_threshold, return_bm=True)
            except ImportError as e:
                print("Could not import PyQmfr: ", e)
                print("Fallback to Collapse via iter. Decimate Operator: ")

                obj = resolve_bmesh(obj, bm) # Resolve Cached bmesh data before continuing

                from .ds_utils import decimate_object, vertex_group_from_outer_boundary

                target_ratio = max(min(initial_reduction / start_tri_cnt, 1.0), 0.0)
                vg = vertex_group_from_outer_boundary(obj)

                decimate_object(obj, target_ratio, vg_name=vg, merge_threshold=merge_threshold)

        obj = clean_mesh_geometry(obj, merge_threshold, bm=bm, return_bm=False) # We resolve the bmesh back to obj in any case here.

        # Report the changes
        final_vert_count = len(obj.data.vertices)
        removed_verts = start_vert_cnt - final_vert_count
        self.report({"INFO"}, f"Mesh cleaning completed: Removed {removed_verts} vertices.")
        self.report({"INFO"}, f"Face count now: {len(obj.data.polygons)}.")
        print(f"Face count now: {len(obj.data.polygons)}.")

        return {"FINISHED"}


class VIEW3D_PT_clean_mesh(bpy.types.Panel):
    """Panel to set parameters and execute mesh cleaning"""
    bl_label = CLEANUP_PANEL_LABEL
    bl_idname = CLEANUP_PANEL_IDNAME
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

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
    if ENV_IS_BLENDER:
        # Ensure pip is available
        ensurepip.bootstrap()

        # Run the installation check
        ensure_package_installed(PYFQMR_MODULE_NAME)

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

    if ENV_IS_BLENDER:
        # Ensure pip is available
        ensurepip.bootstrap()
        print("UNINSTALLING PYFQMR")
        # Uninstall xatlas
        uninstall_package(PYFQMR_MODULE_NAME)



if __name__ == "__main__":
    register()
