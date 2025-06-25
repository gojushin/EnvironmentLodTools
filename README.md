# Environment LOD Tools

[![Blender Plugins](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/build-plugins.yml/badge.svg)](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/build-plugins.yml)
[![Standalone](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/build-release.yml/badge.svg)](https://github.com/gojushin/EnvironmentLodTools/actions/workflows/build-release.yml)

<p align="center">
  <img width="256" height="256" src="https://raw.githubusercontent.com/gojushin/EnvironmentLodTools/main/docs/resources/icon.svg" alt="Logo">
</p>

This is a collection of plugins for [Blender](https://www.blender.org/) (v. 4.2.0 and above).
The plugins are designed to help with the creation of environment levels of detail (LODs) for terrestrial photogrammetry models.
(Models of Landscapes, Cities, and other "flat" structures).

<p align="center">
  <img width="960" height="410" src="https://raw.githubusercontent.com/gojushin/EnvironmentLodTools/main/docs/resources/enviro_lod_tools_example.jpg" alt="LOD Example logo">
</p>

The tool is split into several single plugins, that can be used independently of each other.
There is also a combined plugin that can load a model from the file system and generate LODs for it, without actively rendering it to the viewport.
**This is essential for source files that are too massive to display in the viewport.**

**Blender Plugins** are available for `Windows`, `Linux` and `Mac (experimental)`.
 
For Windows there is also a self-contained, zero-config GUI application available.

### Features

- **Cleanup**: Cleans/Preprocesses the mesh for use in the LOD pipeline. All mesh operations are done using the BMesh framework to ensure performance. [Pyfqmr](https://github.com/Kramer84/pyfqmr-Fast-Quadric-Mesh-Reduction) is used for mesh reduction.


- **Mesh Slicer**: Cuts a mesh into a user-defined amount of square slices. (This reimplements Blenders Bisect logic in a way that does not require to duplicate the mesh in order to keep both half's)


- **LOD Pipeline**: Generates the levels of detail (LODs) for all the selections using [pyfqmr](https://github.com/Kramer84/pyfqmr-Fast-Quadric-Mesh-Reduction) again. The LOD generation retains the borders of the highest LOD for flawless LOD transitions of individual modules.


- **XAtlas Unwrapper**: Unwraps the model using the [xatlas-python](https://github.com/mworchel/xatlas-python) bindings. Utilizes multiprocessing to speed up the unwrapping of multiple meshes significantly.


- **Baker**: Transfers the base color of a defined mesh onto one or multiple selected meshes. Blender is used as the baking framework.


# Installation

<p align="start">
    <img width="509" height="475" src="https://raw.githubusercontent.com/gojushin/EnvironmentLodTools/main/docs/resources/enviro_lod_tools_gui_example.jpg" alt="GUI Example">
</p>

## GUI
EnvironmentLodTools can also be used with a "standalone" PySide6 based GUI.
It exposes the exact same parameters, but uses a small C++ Launcher targeting an embedded Python install, with Blender as a module.

To use the GUI do the following:
1. Download the `enviro_gui[...].zip` from the [latest release](https://github.com/gojushin/EnvironmentLodTools/releases).
2. Run the contained .exe file.

## Plugin
To install the plugins, follow these steps:

1. Download the [latest release](https://github.com/gojushin/EnvironmentLodTools/releases/latest) from GitHub.
2. In Blender, go to `Edit` -> `Preferences` -> `Add-ons` and click on the `Install from lokal disk` hidden in the submenu on the top right.
3. Select the .zip file from the download folder.
4. Enable the plugins by checking the plugins checkbox.
5. Once installed, the plugins can be accessed through the `Tool` and `Tools` panel.

### Building 

#### Using the provided scripts

- Run `build.sh` using a applicable shell (i.e. GitShell, MinGW64, MSYS2, etc...)
> [!NOTE]  
> **build.sh** takes two additional _optional_ arguments:
> 
> `--blender` (which lets you define the fielpath to the blender installation to use for plugin building.)
> 
> `--python-version` (which lets you define the python version for building. i.e.: `3.11.9`)

#### Building from scratch

- Download the correct wheels [pyfqmr](https://pypi.org/project/pyfqmr/#files) and [xatlas](https://pypi.org/project/xatlas/#files) for your correct platform and python version an place them in `.plugin_src/wheels`
- Add the path(s) to the wheels to the blender manifest at `.plugin_src/blender_manifest.toml`
- Ensure you have Blender installed.
- Build the Plugin using Blenders build command:
  ```shell
  blender --command extension build
  ```
   See also: [Blender Docs](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html)


- Ensure the plugins name has the correct naming depending on your target platform:
  - Win: `windows_x64.zip`
  - OSX: `macos_arm64.zip`
  - Linux: `linux_x64.zip`


- Download the desired [embeddable python package](https://www.python.org/downloads/windows/).
- Unpack it to `.python_embed/`, unless you change the path in the `launcher.cpp`.
- Enable Site Support by either using Powershell or Bash. Do this by running one of the following commands inside the directory where there embedded python exectuable lives.

  ```powershell
  -Command "(Get-Content python*._pth) -replace '^#import site', 'import site' | Set-Content python*._pth"
  ```
  
  or
  
  ```bash
  sed -i 's/^#import site/import site/' python*._pth
  ```

- Install pip into the embeddable Python:
  - Download get-pip.py from [here](https://bootstrap.pypa.io/pip/get-pip.py).
  - Navigate to the directory the embeddable `python.exe` is located, place the downloaded file here and run:
    ```shell
    python.exe get-pip.py
    ```
- Using the embeddable Python Pip install the [Blender as a module](https://pypi.org/project/bpy/) and [PySide](https://pypi.org/project/PySide6/)
  ```shell
  python.exe -m pip install bpy
  python.exe -m pip install PySide6
  ```

- Build the launcher using CMake (We are using MinGW, but you can use any Compiler you please):
  ``` 
  cmake -G "MinGW Makefiles" ..
  cmake --build .
  ```
  
- Ensure the folder structure looks as follows:
  ```
  📁 root
  ├── 📄 launcher.exe
  ├── 📄 enviro_tools_gui.py
  ├── 📄 styles.qss (optional)
  ├── 📄 blender_plugin_windows_x64.zip
  ├── 📁 python_embed/
  │   └── 📄 ...
  └── 📁 plugin_src/
      └── 📄 ...
  ```

### Known Issues

#### The UI freezes once "Start" is pressed in the GUI

This behavior occurs because, in Python, two event loops cannot run concurrently in the same thread. This limitation stems from the environment in which the application is currently executed. I plan to address this in a future update by running the two event loops of PySide and Blender-as-a-module in separate threads and connecting them via IPC.

Do not worry though, since even if the GUI freezes, the processing will still take place. As a workaround for now, I instead made the console visible.

### Contributing

Contributions are welcome! If you find any bugs or have suggestions for improvements, please open an issue or submit a pull request.

### License

The code is licensed under the [GPLv3 License](LICENSE).

### Credits

This project was originally created by [Nico Breycha](https://github.com/gojushin) ([High Vision](https://high-vision.de)) for the [Deine Stadt](https://deinestadt.science/) project.

3rd party libraries used in this project are licensed under their own licenses.
- [xatlas-python](https://github.com/mworchel/xatlas-python) bindings, licensed under the [MIT License](https://github.com/mworchel/xatlas-python/blob/master/LICENSE).
  - (Original [xatlas](https://github.com/jpcy/xatlas) Implementation by [jpcy](https://github.com/jpcy))


- [pyfqmr](https://github.com/Kramer84/pyfqmr-Fast-Quadric-Mesh-Reduction), licensed under the [MIT License](https://github.com/Kramer84/pyfqmr-Fast-Quadric-Mesh-Reduction/blob/master/LICENSE)
  - (Original [Fast-Quadric-Mesh-Simplification](https://github.com/sp4cerat/Fast-Quadric-Mesh-Simplification) implementation by [sp4cerat](https://github.com/sp4cerat))


- [Blender](https://www.blender.org/), licensed under the [GPLv2 License](https://www.blender.org/about/license/)


- [Pyside6](https://pypi.org/project/PySide6/), licensed under the [LGPLv3/GPLv3](https://github.com/pyside6/pyside6/blob/master/LICENSE)

### Older Versions

As of June 2025 I no longer support Blender Versions 4.1 and below. The latest release for these versions can be found [here](https://github.com/gojushin/EnvironmentLodTools/releases/tag/0.0.55-pre).