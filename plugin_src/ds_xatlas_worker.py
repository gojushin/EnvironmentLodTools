"""
XAtlas UV Unwrapping Utilities for Blender Integration.

This module provides multiprocessing-safe wrappers around the `xatlas` library
for automated UV unwrapping of 3D meshes. It is designed to work both within Blender
(using its embedded Python environment) and as a standalone module.
"""


import os
import sys
import traceback
import contextlib
import multiprocessing as mp

WORKER_DIR = os.path.dirname(os.path.abspath(__file__))
BLENDER_KWORDS = ["blender", "scripts/modules", "scripts/startup", "bpy"]


# region private

def _test_xatlas(process_id):
    """
    Perform a test of the XAtlas library by running a simple UV parametrization
    on a basic triangle mesh. Intended for use in multiprocessing to verify installation integrity.

    :param process_id: Identifier for the process executing the test (used for error reporting).
    :type process_id: int
    :returns: A tuple (success, error_message). `success` is True if test passed, False otherwise.
              `error_message` is None on success, or a formatted traceback string on failure.
    :rtype: tuple[bool, str or None]
    """
    try:
        # Test import
        import xatlas
        import numpy as np

        # Test actual xatlas functionality with a simple mesh
        # Create a simple triangle mesh
        vertices = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 1.0, 0.0]
        ], dtype=np.float32)

        faces = np.array([[0, 1, 2]], dtype=np.uint32)

        # Try to parametrize it
        vmapping, indices, uvs = xatlas.parametrize(vertices, faces)

        # Verify we got valid results
        if uvs is None or len(uvs) == 0:
            raise RuntimeError("XAtlas parametrization returned empty UVs")

        # Check that we have the expected number of UV coordinates
        if len(uvs) < 3:
            raise RuntimeError(f"Expected at least 3 UV coordinates, got {len(uvs)}")

        return True, None
    except ImportError as e:
        return False, f"Import error in process {process_id}: {traceback.format_exc()}"
    except Exception as e:
        return False, f"Runtime error in process {process_id}: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"


def _process_with_xatlas(data):
    """
    Execute UV parametrization for a single mesh using the XAtlas library.

    :param data: A tuple containing (object_name, vertices, faces).
                 - `object_name` is a string identifier.
                 - `vertices` is a NumPy array of shape (N, 3) representing 3D coordinates.
                 - `faces` is a NumPy array of shape (M, 3) representing triangle indices.
    :type data: tuple[str, numpy.ndarray, numpy.ndarray]
    :returns: A tuple (object_name, vmapping, indices, uvs, error_message), where:
              - `vmapping`, `indices`, and `uvs` are lists (or None on failure).
              - `error_message` contains a traceback string on failure, or None on success.
    :rtype: tuple[str, list or None, list or None, list or None, str or None]
    """
    obj_name, vertices, faces = data
    try:
        import xatlas
        vmapping, indices, uvs = xatlas.parametrize(vertices, faces)
        return obj_name, vmapping.tolist(), indices.tolist(), uvs.tolist(), None
    except Exception as e:
        return obj_name, None, None, None, traceback.format_exc()


# endregion

# region public

@contextlib.contextmanager
def multiprocessing_safeguard(paths_to_make_available, blender_bin=None):
    """
    Context manager to prepare a clean multiprocessing environment
    for use outside or inside Blender's own python environment.

    It sanitizes `sys.path` and `sys.modules` by removing Blender-specific paths or modules when
    running as an external module.

    Automatically restores the original sys.path and sys.modules upon exit.

    :param paths_to_make_available: A path or list of paths to be added to `sys.path` inside the context.
    Use these to expose your functionality to child processes.
    :type paths_to_make_available: str or list[str]
    :param blender_bin: Path to the Blender executable if running inside Blender (used to detect plugin mode).
    :type blender_bin: str or None
    :yield: Yields control back to the calling context with modified `sys.path` and `sys.modules`.
    :rtype: None
    """
    # If only a string was passed, put it inside a list.
    if isinstance(paths_to_make_available, str):
        paths_to_make_available = [paths_to_make_available]

    # Store original values for later restore
    original_sys_path = sys.path.copy()
    original_sys_modules = sys.modules.copy()

    try:
        cleaned_sys_path = []

        for path in sys.path:
            path_lower = path.lower()

            if not blender_bin:
                # If we operate as a module we need to remove all blender related paths.
                # Our own Python Environment has everything we need.
                if not any(kw in path_lower for kw in BLENDER_KWORDS):
                    cleaned_sys_path.append(path)
            else:
                # If we are operating as plugin we need all references to blenders python environment.
                cleaned_sys_path.append(path)

        # Add all the paths to make available.
        for path in paths_to_make_available:
            cleaned_sys_path.insert(0, path)

        sys.path = cleaned_sys_path

        # Remove bpy-related modules from sys.modules to prevent inheritance
        modules_to_remove = [mod for mod in sys.modules if mod.startswith('bpy') or mod == '_bpy']
        for mod in modules_to_remove:
            sys.modules.pop(mod, None)

        if blender_bin:
            # When running as plugin in Blender remove everything with bl_ext namespace.
            plugin_modules_to_remove = [mod for mod in sys.modules if mod.startswith('bl_ext') or mod == '_bl_ext']
            for mod in plugin_modules_to_remove:
                sys.modules.pop(mod, None)

        try:
            # Ensure spawn method is used (required on Windows)
            mp.set_start_method('spawn', force=True)
        except RuntimeError:
            pass  # Already set

        yield

    finally:
        # Restore original state
        sys.path = original_sys_path
        sys.modules.clear()
        sys.modules.update(original_sys_modules)


def unwrap_multi(mesh_data_list, xatlas_path, context=None, blender_path=None):
    """
    Unwrap multiple meshes using XAtlas in parallel using Python's multiprocessing module.

    :param mesh_data_list: A list of tuples (name, vertices, faces) for each mesh to unwrap.
    :type mesh_data_list: list[tuple[str, np.ndarray, np.ndarray]]
    :param xatlas_path: Path to the directory containing the `xatlas` module.
    :type xatlas_path: str
    :param context: Blender context used to update progress bar (optional).
    :type context: bpy.types.Context or None
    :param blender_path: Path to the Blender binary if running inside Blender.
    :type blender_path: str or None
    :returns: A list of results, each being a tuple of (name, vmapping, indices, uvs, error).
    :rtype: list[tuple[str, list, list, list, str or None]]
    :raises ValueError: If the XAtlas path is not provided.
    """
    if not xatlas_path:
        raise ValueError("XAtlas Path not provided.")

    total_meshes = len(mesh_data_list)

    with multiprocessing_safeguard([WORKER_DIR, xatlas_path], blender_bin=blender_path):
        # Create multiprocessing pool with optimal number of processes
        num_processes = min(mp.cpu_count(), len(mesh_data_list), 8)  # Cap at 8 to avoid overhead
        with mp.Pool(processes=num_processes) as pool:
            import ds_xatlas_worker
            # Process all meshes in parallel
            results = pool.map(ds_xatlas_worker._process_with_xatlas, mesh_data_list)
            if context:
                # Update progress (will show completion since multiprocessing doesn't allow real-time updates)
                context.window_manager.progress_update(total_meshes)

    return results


def unwrap_single(mesh_data_list, context=None):
    """
    Unwrap multiple meshes serially using XAtlas in a single process.

    :param mesh_data_list: A list of tuples (name, vertices, faces) for each mesh to unwrap.
    :type mesh_data_list: list[tuple[str, np.ndarray, np.ndarray]]
    :param context: Blender context used to update progress bar (optional).
    :type context: bpy.types.Context or None
    :returns: A list of results, each being a tuple of (name, vmapping, indices, uvs, error).
    :rtype: list[tuple[str, list, list, list, str or None]]
    """
    results = []

    for i, data in enumerate(mesh_data_list):
        results.append(_process_with_xatlas(data))

        if context:
            context.window_manager.progress_update(i + 1)

    return results


def test_xatlas_mp_viability(xatlas_path, blender_path=None):
    """
    Tests whether the XAtlas module is correctly installed and functional using multiprocessing.

    :param xatlas_path: Path to the directory containing the `xatlas` module.
    :type xatlas_path: str
    :param blender_path: Path to the Blender binary if running inside Blender (optional).
    :type blender_path: str or None
    :returns: True if XAtlas works correctly in subprocesses, False otherwise.
    :rtype: bool
    """
    try:
        with multiprocessing_safeguard([WORKER_DIR, xatlas_path], blender_bin=blender_path):
            # Get addon directory for worker module
            with mp.Pool(processes=2) as pool:
                import ds_xatlas_worker
                results = pool.map(ds_xatlas_worker._test_xatlas, [0, 1])  # Test on 2 processes

                # Check if all tests passed
                success = all(result[0] for result in results)
                if not success:
                    for i, (passed, error) in enumerate(results):
                        if error:
                            return False
                else:
                    return success
    except Exception:
        return False

# endregion

if __name__ == '__main__':
    mp.freeze_support()
    mp.set_start_method("spawn")