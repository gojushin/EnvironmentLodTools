# Environment LOD Tools

This is a collection of plugins for [Blender](https://www.blender.org/) (v. 4.0.0 and above).
The plugins are designed to help with the creation of environment levels of detail (LODs) for terrestrial photogrammetry models.
(Models of Landscapes, Cities, and other "flat" structures).

The plugin is split into several single plugins, that can be used independently of each other.
There is also a combined plugin that can load a model from the file system and generate LODs for it, without actively rendering it to the viewport.
**This is essential for source files that are too massive to display in the viewport.**

A version that runs entirely headless is also planned.

### Features

- **Cleanup**: Cleans/Preprocesses the mesh for use in the LOD pipeline.
- **Mesh Slicer**: Cuts a mesh into a user-defined amount of square slices.
- **LOD Pipeline**: Generates the levels of detail (LODs) for all the selections using the provided settings.
- **XAtlas Unwrapper**: Unwraps the model using the [xatlas-python](https://github.com/mworchel/xatlas-python) bindings.
- **Baker**: Transfers the base color of a defined mesh onto one or multiple selected meshes.


### Installation

To install the plugins, follow these steps:

1. Download the [latest release](https://github.com/gojushin/EnvironmentLodTool/releases/latest) from GitHub.
2. Downloaded zip file.
3. In Blender, go to `Edit` -> `Preferences` -> `Add-ons` and click on the `Install` button.
4. Select the .zip file from the download folder.
5. Enable the plugins by checking the plugins checkbox. *Note: This invokes pip to install xatlas to your local environment and can therefore cause Blender to hang for a second.*

### Usage

Once installed, the plugins can be accessed through the `Tool` panel.

### Contributing

Contributions are welcome! If you find any bugs or have suggestions for improvements, please open an issue or submit a pull request.

### License

The code is licensed under the [GPLv3 License](LICENSE).

### Credits

This project was created by [Nico Breycha](https://github.com/gojushin).
