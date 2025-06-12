# ds_xatlas_worker.py

import sys
import traceback


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
        return obj_name, None, None, None, str(e)

if __name__ == '__main__':
    pass