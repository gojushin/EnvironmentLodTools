# Environment LOD Tools

Blender 4.0.0

[![Linux Build/Release (Python 3.10)](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/deploy_zip_files_3_10_linux.yml/badge.svg)](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/deploy_zip_files_3_10_linux.yml)
[![Windows Build/Release (Python 3.10)](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/deploy_zip_files_3_10_win.yml/badge.svg)](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/deploy_zip_files_3_10_win.yml)

Blender 4.1.0 and above

[![Linux Build/Release (Python 3.11)](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/deploy_zip_files_3_11_linux.yml/badge.svg)](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/deploy_zip_files_3_11_linux.yml)
[![Windows Build/Release (Python 3.11)](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/deploy_zip_files_3_11_win.yml/badge.svg)](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/deploy_zip_files_3_11_win.yml)

<p align="center">
  <img width="960" height="410" src="https://raw.githubusercontent.com/gojushin/EnvironmentLodTools/main/docs/resources/enviro_lod_tools_example.jpg" alt="LOD Example logo">
</p>

This is a collection of plugins for [Blender](https://www.blender.org/) (v. 4.0.0 and above).
The plugins are designed to help with the creation of environment levels of detail (LODs) for terrestrial photogrammetry models.
(Models of Landscapes, Cities, and other "flat" structures).

The tool is split into several single plugins, that can be used independently of each other.
There is also a combined plugin that can load a model from the file system and generate LODs for it, without actively rendering it to the viewport.
**This is essential for source files that are too massive to display in the viewport.**

### Features

- **Cleanup**: Cleans/Preprocesses the mesh for use in the LOD pipeline. All mesh operations are done using the BMesh framework to ensure performance. [Pyfqmr](https://github.com/Kramer84/pyfqmr-Fast-Quadric-Mesh-Reduction) is used for mesh reduction.


- **Mesh Slicer**: Cuts a mesh into a user-defined amount of square slices. (This reimplements Blenders Bisect logic in a way that does not require to duplicate the mesh in order to keep both halfs)


- **LOD Pipeline**: Generates the levels of detail (LODs) for all the selections using [pyfqmr](https://github.com/Kramer84/pyfqmr-Fast-Quadric-Mesh-Reduction) again. The LOD generation retains the borders of the highest LOD for flawless LOD transitions of individual modules.


- **XAtlas Unwrapper**: Unwraps the model using the [xatlas-python](https://github.com/mworchel/xatlas-python) bindings.


- **Baker**: Transfers the base color of a defined mesh onto one or multiple selected meshes. Blender is used as the baking framework.


# Installation

<p align="start">
    <img width="509" height="475" src="https://raw.githubusercontent.com/gojushin/EnvironmentLodTools/main/docs/resources/enviro_lod_tools_gui_example.jpg" alt="GUI Example">
</p>

## GUI
EnvironmentLodTools can also be used with a "standalone" PySide6 based GUI.
It exposes the exact same parameters, but uses the users local Python install, with Blender as a module, instead of Blenders Embedded Python.

To use the GUI do the following:
1. Download the entire `source code` from the [latest release](https://github.com/gojushin/EnvironmentLodTools/releases).
2. Open the command prompt.
3. Run `pip install -r requirnments.txt` in the directory of the plugin.
4. Start the GUI by executing `enviro_tools_gui.py`

Note: When starting the GUI for the first time, it will take a few moments to build the python modules.

## Plugin
To install the plugins, follow these steps:

1. Download the [latest release](https://github.com/gojushin/EnvironmentLodTool/releases/latest) from GitHub.
2. In Blender, go to `Edit` -> `Preferences` -> `Add-ons` and click on the `Install` button.
3. Select the .zip file from the download folder.
4. Enable the plugins by checking the plugins checkbox. 

*Note: Enabling the plugins for the first time will take a few moments since two python modules will be built in place in Blenders Python install.*

### Usage

Once installed, the plugins can be accessed through the `Tool` and `Tools` panel.

To use the GUI, download the source code and execute the `enviro_tools_gui.py` file.

_Note: Since Blender is non-thread safe by nature, the GUI will currently freeze upon starting the pipeline.
You can track the progress in the CLI._

### Contributing

Contributions are welcome! If you find any bugs or have suggestions for improvements, please open an issue or submit a pull request.

### License

The code is licensed under the [GPLv3 License](LICENSE).

### Credits

This project was created by [Nico Breycha](https://github.com/gojushin).

3rd party libraries used in this project are licensed under their own licenses.
- [xatlas-python](https://github.com/mworchel/xatlas-python) bindings, licensed under the [MIT License](https://github.com/mworchel/xatlas-python/blob/master/LICENSE).
  - (Original [xatlas](https://github.com/jpcy/xatlas) Implementation by [jpcy](https://github.com/jpcy))


- [pyfqmr](https://github.com/Kramer84/pyfqmr-Fast-Quadric-Mesh-Reduction), licensed under the [MIT License](https://github.com/Kramer84/pyfqmr-Fast-Quadric-Mesh-Reduction/blob/master/LICENSE)
  - (Original [Fast-Quadric-Mesh-Simplification](https://github.com/sp4cerat/Fast-Quadric-Mesh-Simplification) implementation by [sp4cerat](https://github.com/sp4cerat))


- [Blender](https://www.blender.org/), licensed under the [GPLv2 License](https://www.blender.org/about/license/)


- [Pyside6](https://pypi.org/project/PySide6/), licensed under the [LGPLv3/GPLv3](https://github.com/pyside6/pyside6/blob/master/LICENSE)
