"""
XAtlas Unwrapper Add-on for Blender
This module implements an operator to unwrap UVs using xatlas in Blender.
"""

import os
import traceback

import numpy as np
import bpy
import bmesh

from .ds_consts import UNWRAP_IDNAME, UNWRAP_LABEL, UNWRAP_PANEL_LABEL, UNWRAP_PANEL_IDNAME
from .ds_xatlas_worker import test_xatlas_mp_viability, unwrap_multi, unwrap_single

BLENDER_BIN_PATH = bpy.app.binary_path # None if running as module.

bl_info = {
    "name": "XAtlas Unwrapper",
    "author": "Nico Breycha",
    "version": (0, 1, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Unwraps the model using xatlas.",
    "category": "Object",
}


class MESH_OT_unwrap_xatlas(bpy.types.Operator):
    """Unwrap UVs using xatlas"""
    bl_idname = UNWRAP_IDNAME
    bl_label = UNWRAP_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cnt_fail = 0
        mesh_data_list = []
        obj_map = {}
        messages = []

        # Prepare data
        for obj in context.selected_objects:
            if obj.type != "MESH":
                messages.append(f"Skipping {obj.name}: not a mesh")
                cnt_fail += 1
                continue

            mesh = obj.data
            if len(mesh.polygons) == 0:
                messages.append(f"Skipping {obj.name}: empty mesh")
                cnt_fail += 1
                continue

            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])

            vertices = np.array([v.co[:] for v in bm.verts], dtype=np.float32)
            faces = np.array([[v.index for v in f.verts] for f in bm.faces], dtype=np.uint32)

            mesh_data_list.append((obj.name, vertices, faces))

            bm.to_mesh(mesh)
            mesh.update()
            obj_map[obj.name] = obj

            bm.free()

        # Cancel if no data
        if not mesh_data_list:
            self.report({"WARNING"}, "No valid meshes to process")
            return {"CANCELLED"}

        # Prepare UI
        total_meshes = len(mesh_data_list)
        context.window_manager.progress_begin(0, total_meshes)

        # Check and Prepare XAtlas
        xatlas_path = ""
        try:
            import xatlas
            xatlas_path = os.path.dirname(xatlas.__file__)
        except ImportError:
            self.report({"WARNING"}, "XAtlas is not available.")
            return {"CANCELLED"}

        # Determine multiprocessing viability.
        mp_is_viable = test_xatlas_mp_viability(xatlas_path, BLENDER_BIN_PATH)
        results = []
        used_single_processing = False

        if mp_is_viable:
            # Multiprocessing
            try:
                results = unwrap_multi(mesh_data_list, xatlas_path, context, BLENDER_BIN_PATH)
            except Exception as e:
                # Fallback to single processing if multiprocessing fails
                messages.append(f"Multiprocessing failed ({str(e)}), falling back to single processing")
                results = unwrap_single(mesh_data_list, context)
                used_single_processing = True
        else:
            results = unwrap_single(mesh_data_list, context)
            used_single_processing = True

        # Apply resulting UVs
        for result in results:
            obj_name, vmapping, indices, uvs, error = result

            if error:
                tb_str = error if isinstance(error, str) else ''.join(
                    traceback.format_exception(None, error, error.__traceback__))
                messages.append(f"Failed to parametrize {obj_name}:\n{tb_str}")

                cnt_fail += 1
                continue

            obj = obj_map.get(obj_name)
            if not obj:
                messages.append(f"Object {obj_name} not found in context")
                cnt_fail += 1
                continue

            mesh = obj.data
            bm = bmesh.new()
            bm.from_mesh(mesh)

            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                uv_layer = bm.loops.layers.uv.new()

            indices = np.array(indices, dtype=np.uint32)
            uvs = np.array(uvs, dtype=np.float32)

            try:
                for face, tri_indices in zip(bm.faces, indices):
                    for loop, vert_index in zip(face.loops, tri_indices):
                        if vert_index < len(uvs):
                            loop[uv_layer].uv = uvs[vert_index][:2]
            except Exception as e:
                messages.append(f"Error applying UVs for {obj_name}: {str(e)}")
                cnt_fail += 1
                bm.free()
                continue

            bm.to_mesh(mesh)
            mesh.update()
            bm.free()

        context.window_manager.progress_end()
        total_processed = total_meshes - cnt_fail

        messages.append(f"UVs generated successfully for {total_processed} meshes. {cnt_fail} objects skipped. "
                        f"Used {'single processing' if used_single_processing else 'multi processing'}.")

        for msg in messages:
            self.report({"INFO"}, msg)

        return {"FINISHED"}


class VIEW3D_PT_unwrap_xatlas(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = UNWRAP_PANEL_LABEL
    bl_idname = UNWRAP_PANEL_IDNAME
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.operator(UNWRAP_IDNAME)


classes = (MESH_OT_unwrap_xatlas, VIEW3D_PT_unwrap_xatlas)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)


def unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)

if __name__ == "__main__":
    register()