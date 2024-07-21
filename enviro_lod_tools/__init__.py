from .addons import (ds_blender_lod_plug, ds_blender_slice_plug, ds_blender_xatlas_plug, ds_blender_baker_plug,
                     ds_blender_cleanup_plug, ds_blender_combined_plugin)


bl_info = {
    "name": "Environment LOD Tools",
    "author": "Nico Breycha",
    "version": (0, 0, 127),
    "blender": (4, 0, 0),
    "description": "Generates LODs for selected mesh objects across multiple scripts.",
    "category": "Object",
}


def register():
    ds_blender_cleanup_plug.register()
    ds_blender_slice_plug.register()
    ds_blender_lod_plug.register()
    ds_blender_xatlas_plug.register()
    ds_blender_baker_plug.register()
    ds_blender_combined_plugin.register()


def unregister():
    ds_blender_cleanup_plug.unregister()
    ds_blender_slice_plug.unregister()
    ds_blender_lod_plug.unregister()
    ds_blender_xatlas_plug.unregister()
    ds_blender_baker_plug.unregister()
    ds_blender_combined_plugin.unregister()


if __name__ == "__main__":
    register()
