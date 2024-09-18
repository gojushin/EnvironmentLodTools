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

import sys
import subprocess
import ensurepip
import importlib.util
import multiprocessing

import numpy as np
import bpy
import bmesh

from .ds_consts import UNWRAP_IDNAME, UNWRAP_LABEL, UNWRAP_PANEL_LABEL, UNWRAP_PANEL_IDNAME

ENV_IS_BLENDER = bpy.app.binary_path != ""

bl_info = {
    "name": "XAtlas Unwrapper",
    "author": "Nico Breycha",
    "version": (0, 0, 4),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Unwraps the model using xatals.",
    "category": "Object",
}

def install_package(package_name):
    python_executable = sys.executable
    try:
        # Execute the pip command to install the package
        subprocess.check_call([python_executable, "-m", "pip", "install", package_name])
        print(f"Successfully installed {package_name}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_name}: {e}")


def is_package_installed(package_name):
    package_spec = importlib.util.find_spec(package_name)
    return package_spec is not None


def ensure_package_installed(package_name):
    if not is_package_installed(package_name):
        print(f"{package_name} is not installed. Installing now...")
        install_package(package_name)
    else:
        print(f"{package_name} is already installed.")


def ensure_xatlas_installed():
    ensure_package_installed("xatlas")


def uninstall_xatlas_package():
    if "xatlas" in sys.modules:
        subprocess.check_call(["pip", "uninstall", "-y", "xatlas"])


def _process_mesh_single_process(data):
    obj_name, vertices, faces = data
    try:
        import xatlas
        # Parametrize the mesh using xatlas
        vmapping, indices, uvs = xatlas.parametrize(vertices, faces)
        return obj_name, vmapping, indices, uvs, None
    except Exception as e:
        # Return the exception message to the main process
        return obj_name, None, None, None, str(e)


def _process_mesh_multiprocessing(data):
    obj_name, vertices, faces = data
    try:
        # Save original sys.path
        original_sys_path = sys.path.copy()

        # Remove Blender-specific paths
        sys.path = [p for p in sys.path if "blender" not in p.lower() and "scripts" not in p.lower()]

        import xatlas  # Import xatlas in the subprocess

        # Restore sys.path
        sys.path = original_sys_path

        # Parametrize the mesh using xatlas
        vmapping, indices, uvs = xatlas.parametrize(vertices, faces)
        # Convert results to lists to make them picklable
        vmapping = vmapping.tolist()
        indices = indices.tolist()
        uvs = uvs.tolist()
        return obj_name, vmapping, indices, uvs, None
    except Exception as e:
        # Return the exception message to the main process
        return obj_name, None, None, None, str(e)


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

        # Prepare data for multiprocessing
        for obj in context.selected_objects:
            if obj.type != "MESH":
                messages.append(f"Skipping {obj.name}: not a mesh")
                cnt_fail += 1
                continue

            mesh = obj.data

            # Skip meshes with 0 polygons
            if len(mesh.polygons) == 0:
                messages.append(f"Skipping {obj.name}: empty mesh")
                continue

            # Create a bmesh object and load the mesh data into it
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])

            # Extract vertex positions and triangle faces from bmesh
            vertices = np.array([v.co[:] for v in bm.verts], dtype=np.float32)
            faces = np.array([[v.index for v in f.verts] for f in bm.faces], dtype=np.uint32)

            # Store data for processing
            mesh_data_list.append((obj.name, vertices, faces))

            # Write the triangulated bmesh back to the original mesh
            bm.to_mesh(mesh)
            mesh.update()

            # Update the object map with the triangulated object
            obj_map[obj.name] = obj

            bm.free()

        if not mesh_data_list:
            self.report({"WARNING"}, "No valid meshes to process")
            return {"CANCELLED"}

        total_meshes = len(mesh_data_list)
        progress = 0

        # Start the progress bar
        context.window_manager.progress_begin(0, total_meshes)

        # Save the original sys.path before importing bpy
        original_sys_path = sys.path.copy()

        try:
            # Restore sys.path to original before starting multiprocessing
            sys.path = [p for p in original_sys_path if "blender" not in p.lower() and "scripts" not in p.lower()]

            # Use multiprocessing Pool
            multiprocessing.freeze_support()

            processes = min(int(multiprocessing.cpu_count() / 4), len(mesh_data_list))

            with (multiprocessing.Pool(processes=processes) as pool):
                # Map the processing function to the data
                results = []
                for result in pool.imap(_process_mesh_multiprocessing, reversed(mesh_data_list)):
                    results.append(result)
                    progress += 1
                    context.window_manager.progress_update(progress)
        except ImportError as e:
            # Multiprocessing not available (This is our fallback for using as plugin)
            self.report({"INFO"}, f"Multiprocessing not available: {e}")
            results = []
            for data in mesh_data_list:
                results.append(_process_mesh_single_process(data))
        except Exception as e:
            self.report({"ERROR"}, f"Multiprocessing failed: {e}")
            context.window_manager.progress_end()
            return {"CANCELLED"}
        finally:
            # Restore sys.path
            sys.path = original_sys_path

        # Apply results
        for result in results:
            obj_name = result[0]
            if result[4]:
                # An error occurred during processing
                error_message = result[4]
                messages.append(f"Failed to parametrize {obj_name}: {error_message}")
                cnt_fail += 1
                continue

            vmapping, indices, uvs = result[1], result[2], result[3]

            obj = obj_map.get(obj_name)
            if not obj:
                messages.append(f"Object {obj_name} not found in context")
                cnt_fail += 1
                continue

            mesh = obj.data

            # Create a new bmesh object and load the mesh data into it
            bm = bmesh.new()
            bm.from_mesh(mesh)

            if not mesh.uv_layers:
                uv_layer = bm.loops.layers.uv.new()
            else:
                uv_layer = bm.loops.layers.uv.active

            # Convert data back to numpy arrays
            indices = np.array(indices, dtype=np.uint32)
            uvs = np.array(uvs, dtype=np.float32)

            # Apply the new UV coordinates based on xatlas output
            for i, face in enumerate(bm.faces):
                loops = face.loops
                tri_indices = indices[i]
                for j, loop in enumerate(loops):
                    new_index = tri_indices[j]
                    loop[uv_layer].uv = (uvs[new_index][0], uvs[new_index][1])

            # Write the changes back to the mesh and update
            bm.to_mesh(mesh)
            mesh.update()
            bm.free()

        context.window_manager.progress_end()
        total_processed = total_meshes - cnt_fail
        messages.append(f"UVs generated successfully for {total_processed} meshes. {cnt_fail} objects skipped.")

        # Show messages
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
    if ENV_IS_BLENDER:
        # Ensure pip is available
        ensurepip.bootstrap()

        # Run the installation check
        ensure_xatlas_installed()

    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)


def unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)

    if ENV_IS_BLENDER:
        # Ensure pip is available
        ensurepip.bootstrap()
        print("UNINSTALLING XATALAS")
        # Uninstall xatlas
        uninstall_xatlas_package()


if __name__ == "__main__":
    register()
