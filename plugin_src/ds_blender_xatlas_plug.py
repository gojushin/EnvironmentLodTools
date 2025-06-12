"""
XAtlas Unwrapper Add-on for Blender
This module implements an operator to unwrap UVs using xatlas in Blender.

**Note on Multiprocessing Issue in Blender on Windows:**
We encountered a problem when using multiprocessing in Blender on Windows.
The issue arises because Blender's Python environment modifies `sys.path` when importing `bpy`,
which interferes with the `multiprocessing` module's ability to spawn new processes that can correctly import modules.
This leads to errors like:

ModuleNotFoundError: No module named '_bpy'

The child processes spawned by `multiprocessing` try to re-import the main module, but due to the modified `sys.path`,
they fail to find the necessary Blender modules.
To mitigate this issue, we manipulate `sys.path` before creating the multiprocessing pool,
ensuring that child processes inherit a clean `sys.path` without Blender-specific paths.
This allows the subprocesses to import the required modules without interference!
For more details on this issue and the workaround, please refer to the following discussion:

https://github.com/TylerGubala/blenderpy/issues/23
"""

import os
import sys
import multiprocessing as mp
from functools import partial
import contextlib

import numpy as np
import bpy
import bmesh

from .ds_consts import UNWRAP_IDNAME, UNWRAP_LABEL, UNWRAP_PANEL_LABEL, UNWRAP_PANEL_IDNAME
from .ds_xatlas_worker import test_xatlas, _process_mesh_multiprocessing


bl_info = {
    "name": "XAtlas Unwrapper",
    "author": "Nico Breycha",
    "version": (0, 0, 6),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Unwraps the model using xatlas.",
    "category": "Object",
}

import datetime
def log_to_file(t):
    with open(r"C:\Users\nibrey\Downloads\log.txt", "a") as f:
        f.write(str(datetime.datetime.now()) + " | " + (t if t != "" else "empty_str") + "\n")


@contextlib.contextmanager
def multiprocessing_safeguard():
    """
    Enhanced context manager for safe multiprocessing in Blender.

    This ensures that:
    1. sys.path is cleaned of Blender-specific paths
    2. The spawn method is explicitly set
    3. The worker module path is properly added
    """
    # Store original values
    original_sys_path = sys.path.copy()
    original_sys_modules = sys.modules.copy()

    try:
        # Clean sys.path of Blender-specific paths
        cleaned_sys_path = []
        for path in sys.path:
            path_lower = path.lower()
            # Keep only non-Blender paths
            if not any(blender_dir in path_lower for blender_dir in
                       ['blender', 'scripts/modules', 'scripts/startup', 'bpy']):
                cleaned_sys_path.append(path)

        # Add the current addon directory to ensure worker module can be found
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        if addon_dir not in cleaned_sys_path:
            cleaned_sys_path.insert(0, addon_dir)

        sys.path = cleaned_sys_path

        # Remove bpy-related modules from sys.modules to prevent inheritance
        modules_to_remove = [mod for mod in sys.modules if mod.startswith('bpy') or mod == '_bpy']
        for mod in modules_to_remove:
            sys.modules.pop(mod, None)

        # Ensure spawn method is used (required on Windows)
        try:
            mp.set_start_method('spawn', force=True)
        except RuntimeError:
            pass  # Already set

        yield

    finally:
        # Restore original state
        sys.path = original_sys_path
        sys.modules.clear()
        sys.modules.update(original_sys_modules)


def _process_mesh_single_process(data):
    obj_name, vertices, faces = data
    try:
        vmapping, indices, uvs = xatlas.parametrize(vertices, faces)
        return obj_name, vmapping.tolist(), indices.tolist(), uvs.tolist(), None
    except Exception as e:
        return obj_name, None, None, None, str(e)


def __init_worker(xatlas_path, addon_dir):
    if addon_dir not in sys.path:
        sys.path.insert(0, addon_dir)
    if xatlas_path not in sys.path:
        sys.path.insert(0, xatlas_path)


def _test_xatlas_viability(xatlas_path):
    """Test if xatlas can be imported and used in multiprocessing context"""
    try:
        from functools import partial
        with multiprocessing_safeguard():
            # Get addon directory for worker module
            addon_dir = os.path.dirname(os.path.abspath(__file__))

            with mp.Pool(processes=2, initializer=__init_worker, initargs=(xatlas_path, addon_dir)) as pool:
                # Use the actual test_xatlas function from worker module
                test_func = partial(test_xatlas, xatlas_path)
                results = pool.map(test_func, [0, 1])  # Test on 2 processes

                # Check if all tests passed
                success = all(result[0] for result in results)
                if not success:
                    for i, (passed, error) in enumerate(results):
                        if error:
                            log_to_file(f"Process {i} failed: {error}")
                return success
    except Exception as e:
        log_to_file(f"Viability check failed: {str(e)}")
        return False

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
            log_to_file(xatlas_path)
        except ImportError:
            self.report({"WARNING"}, "XAtlas is not available.")
            return {"CANCELLED"}

        # Determine multiprocessing viability.
        mp_is_viable = _test_xatlas_viability(xatlas_path)
        log_to_file(str(mp_is_viable))
        log_to_file(str(sys.path))
        results = []

        if mp_is_viable:
            # Multiprocessing
            try:
                with multiprocessing_safeguard():
                    # Create multiprocessing pool with optimal number of processes
                    num_processes = min(mp.cpu_count(), len(mesh_data_list), 8)  # Cap at 8 to avoid overhead
                    log_to_file("Hi")
                    with mp.Pool(processes=num_processes) as pool:
                        # Create a partial function with xatlas_path bound
                        process_func = partial(_process_mesh_multiprocessing, xatlas_path=xatlas_path)

                        # Process all meshes in parallel
                        results = pool.map(process_func, mesh_data_list)

                        # Update progress (will show completion since multiprocessing doesn't allow real-time updates)
                        context.window_manager.progress_update(total_meshes)

            except Exception as e:
                # Fallback to single processing if multiprocessing fails
                messages.append(f"Multiprocessing failed ({str(e)}), falling back to single processing")
                results = [] # Clear before further using.
                for i, data in enumerate(mesh_data_list):
                    results.append(_process_mesh_single_process(data))
                    context.window_manager.progress_update(i + 1)
        else:
            # Single Processing Fallback
            for i, data in enumerate(mesh_data_list):
                results.append(_process_mesh_single_process(data))
                context.window_manager.progress_update(i + 1)

        # Apply resulting UVs
        for result in results:
            obj_name, vmapping, indices, uvs, error = result

            if error:
                messages.append(f"Failed to parametrize {obj_name}: {error}")
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
        messages.append(f"UVs generated successfully for {total_processed} meshes. {cnt_fail} objects skipped.")

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
    mp.freeze_support()
    register()