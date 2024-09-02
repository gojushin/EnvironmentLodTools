import sys
import subprocess
import ensurepip
import importlib.util

import numpy as np
import bpy
import bmesh

from .ds_consts import UNWRAP_IDNAME, UNWRAP_LABEL, UNWRAP_PANEL_LABEL, UNWRAP_PANEL_IDNAME

ENV_IS_BLENDER = bpy.app.binary_path != ""

bl_info = {
    "name": "XAtlas Unwrapper",
    "author": "Nico Breycha",
    "version": (0, 0, 2),
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


# Example function to ensure xatlas is installed
def ensure_xatlas_installed():
    ensure_package_installed("xatlas")


def uninstall_xatlas_package():
    if "xatlas" in sys.modules:
        subprocess.check_call(["pip", "uninstall", "-y", "xatlas"])


class MESH_OT_unwrap_xatlas(bpy.types.Operator):
    """Unwrap UVs using xatlas"""
    bl_idname = UNWRAP_IDNAME
    bl_label = UNWRAP_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    # TODO Implement xatlas.PackOptions and xatlas.ChartOptions
    # See: https://github.com/mworchel/xatlas-python/blob/main/src/options.cpp

    def execute(self, context):
        if "xatlas" not in sys.modules:
            import xatlas

        cnt_succ = 0
        cnt_fail = 0

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                self.report({'WARNING'}, f"Skipping {obj.name}: not a mesh")
                cnt_fail += 1
                continue

            mesh = obj.data

            # Skip valid meshes with 0 polygons
            if len(mesh.polygons) == 0:
                self.report({'INFO'}, f"Skipping {obj.name}: empty mesh")
                continue

            # Get mesh data from the object
            cnt_succ += 1

            # Create a bmesh object and load the mesh data into it
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])

            # Extract vertex positions and triangle faces from bmesh
            vertices = np.array([v.co[:] for v in bm.verts], dtype=np.float32)
            faces = np.array([[v.index for v in f.verts] for f in bm.faces], dtype=np.uint32)

            # Use xatlas to parametrize the mesh
            vmapping, indices, uvs = xatlas.parametrize(vertices, faces)

            # Create a new UV map in the object if it doesn't exist
            if not mesh.uv_layers:
                uv_layer = bm.loops.layers.uv.new()
            else:
                uv_layer = bm.loops.layers.uv.active

            # Applying the new UV coordinates based on xatlas output
            # Iterate over each new triangle and assign uvs
            for i, face in enumerate(bm.faces):
                loops = face.loops
                # Fetch the corresponding new triangle's vertex indices
                tri_indices = indices[i]  # this may need adjustment depending on how `indices` is structured
                for j, loop in enumerate(loops):
                    new_index = tri_indices[j]  # get the new vertex index for the current corner of the triangle
                    loop[uv_layer].uv = (uvs[new_index][0], uvs[new_index][1])

            # Finish up by writing the changes back to the mesh
            bm.to_mesh(mesh)
            mesh.update()  # Update the mesh to reflect the changes
            bm.free()

        self.report({'INFO'}, f"UVs generated successfully for {cnt_succ} meshes. {cnt_fail} objects skipped.")
        return {'FINISHED'}


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
