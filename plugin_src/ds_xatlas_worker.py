import os
import sys
import traceback
import contextlib
import multiprocessing as mp
import datetime
from functools import partial

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))


def log_to_file(t):
    with open(r"C:\Users\nibrey\Downloads\log.txt", "a") as f:
        f.write(str(datetime.datetime.now()) + " | " + (t if t != "" else "empty_str") + "\n")


@contextlib.contextmanager
def multiprocessing_safeguard(xatlas_path):
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
        if ADDON_DIR not in cleaned_sys_path:
            cleaned_sys_path.insert(0, ADDON_DIR)
        if xatlas_path not in cleaned_sys_path:
            cleaned_sys_path.insert(0, xatlas_path)

        sys.path = cleaned_sys_path

        log_to_file("Before:")
        log_to_file(str(sys.modules))
        log_to_file(str(sys.modules))

        # Remove bpy-related modules from sys.modules to prevent inheritance
        modules_to_remove = [mod for mod in sys.modules if mod.startswith('bpy') or mod == '_bpy']
        for mod in modules_to_remove:
            sys.modules.pop(mod, None)

       #region Blender Plugin Only
        plugin_modules_to_remove = [mod for mod in sys.modules if mod.startswith('bl_ext') or mod == '_bl_ext']
        for mod in plugin_modules_to_remove:
            sys.modules.pop(mod, None)

        sys.path.insert(0, ADDON_DIR)

        log_to_file("\nAfter:")
        log_to_file(str(sys.modules))
        log_to_file(str(sys.path))

        sys.path.insert(0, r"C:\Program Files\Blender Foundation\Blender 4.4\4.4\python\DLLs")
        os.add_dll_directory(r"C:\Program Files\Blender Foundation\Blender 4.4\4.4\python\DLLs")
        sys.path.insert(0, r"C:\Program Files\Blender Foundation\Blender 4.4\4.4\python\lib")
        sys.path.insert(0, r"C:\Program Files\Blender Foundation\Blender 4.4\4.4\python\lib\site-packages")

        # endregion

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
        import xatlas
        vmapping, indices, uvs = xatlas.parametrize(vertices, faces)
        return obj_name, vmapping.tolist(), indices.tolist(), uvs.tolist(), None
    except Exception as e:
        return obj_name, None, None, None, traceback.format_exc()


def unwrap_multi(mesh_data_list, xatlas_path, context=None):
    if not xatlas_path:
        raise ValueError("XAtlas Path not provided.")

    total_meshes = len(mesh_data_list)

    with multiprocessing_safeguard(xatlas_path):
        # Create multiprocessing pool with optimal number of processes
        num_processes = min(mp.cpu_count(), len(mesh_data_list), 8)  # Cap at 8 to avoid overhead
        log_to_file("Hi")
        with mp.Pool(processes=num_processes) as pool:
            import ds_xatlas_worker
            # Create a partial function with xatlas_path bound
            process_func = partial(ds_xatlas_worker._process_mesh_multiprocessing, xatlas_path=xatlas_path)

            # Process all meshes in parallel
            results = pool.map(process_func, mesh_data_list)
            if context:
                # Update progress (will show completion since multiprocessing doesn't allow real-time updates)
                context.window_manager.progress_update(total_meshes)

    return results


def unwrap_single(mesh_data_list, context=None):
    results = []
    for i, data in enumerate(mesh_data_list):
        results.append(_process_mesh_single_process(data))
        if context:
            context.window_manager.progress_update(i + 1)

    return results


def test_xatlas_viability(xatlas_path):
    """Test if xatlas can be imported and used in multiprocessing context"""
    try:
        from functools import partial
        with multiprocessing_safeguard(xatlas_path):
            # Get addon directory for worker module
            with mp.Pool(processes=2) as pool:
                import ds_xatlas_worker

                # Use the actual test_xatlas function from worker module
                test_func = partial(ds_xatlas_worker.test_xatlas, xatlas_path)
                results = pool.map(test_func, [0, 1])  # Test on 2 processes

                # Check if all tests passed
                success = all(result[0] for result in results)
                if not success:
                    for i, (passed, error) in enumerate(results):
                        if error:
                            log_to_file(f"Process {i} failed: {error}")
                return success
    except Exception as e:
        log_to_file(f"Viability check failed: \n{traceback.format_exc()}")
        return False


def test_xatlas(xatlas_path, process_id):
    """
    Function used by multiprocessing to test xatlas import and functionality in child processes.
    Tests both import and basic parametrization to ensure xatlas is fully functional.
    Must not import bpy!
    """
    try:
        if xatlas_path not in sys.path:
            sys.path.insert(0, xatlas_path)

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


def _process_mesh_multiprocessing(data, xatlas_path):
    """
    This is used in the real unwrap phase via multiprocessing.
    Must not import bpy!
    """
    obj_name, vertices, faces = data
    try:
        if xatlas_path not in sys.path:
            sys.path.insert(0, xatlas_path)
        import xatlas
        vmapping, indices, uvs = xatlas.parametrize(vertices, faces)
        return obj_name, vmapping.tolist(), indices.tolist(), uvs.tolist(), None
    except Exception as e:
        return obj_name, None, None, None, traceback.format_exc()


if __name__ == '__main__':
    mp.freeze_support()
    mp.set_start_method("spawn")