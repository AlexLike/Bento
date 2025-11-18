
![](logo.png)
A Blender to [Nori](https://github.com/wjakob/nori) export plugin. Inspired by [BlenderNoriPlugin](https://github.com/Phil26AT/BlenderNoriPlugin) but written from scratch for Blender 4.5+ with some additional features.

## Features

- Exports Blender scenes to Nori (XML) format
- Exports meshes as obj
    - Supports meshes with multiple materials
- Exports basic materials (diffuse, glossy/microfacet, glass/dielectric)
- Exports emissive materials as area lights
- Option to export all referenced image textures as PNG or JPEG
- Simple settings for resolution, SPP, integrator, reconstruction filter, etc.
- Easily extensible for other simple nodes/shaders
- Exports point lights

## Installation

1. Download the latest release from the [releases page](https://github.com/TheCodecOfficial/Bento/releases/latest).
2. In Blender, go to `Edit > Preferences > Add-ons > Install...`
3. Select the downloaded ZIP file and click `Install Add-on`.
4. Enable the add-on by checking the box next to "Bento" in the add-ons list.
5. Save preferences if desired.

## Usage

To export a scene as a Nori XML, first make sure you're in object mode. Then go to `File > Export > Nori (.xml)`. Choose a path and filename, and adjust the export settings as needed. Then click `Export Nori XML`.

![export settings](export_settings.png)

> [!IMPORTANT]  
> Currently, every mesh needs to be UV unwrapped, otherwise it will cause a segmentation fault in Nori. You can unwrap a mesh by selecting it and pressing `tab`, then `U` to bring up the unwrap menu (choose any option). After unwrapping, make sure to exit edit mode by pressing `tab` again.

## Limitations

### Shaders

Currently, only diffuse, glossy (microfacet) and glass (dielectric) shaders are supported. Glossy shaders with a very low roughness will get converted to a mirror shader in Nori.

> [!NOTE]
> Blender's glossy shader doesn't have a diffuse lobe. To get equivalent behavior in Nori, kd automatically gets set to black (0, 0, 0). Also, the color parameter of Blender's glossy shader has no counterpart in Nori's microfacet shader, so it will be ignored. Set it to white (1, 1, 1) to match Nori's behavior (the default in blender is (0.8, 0.8, 0.8)!). Finally, set the distribution to "Beckmann" to match Nori's implementation.

> [!NOTE]
> Nori's default dielectric shader is smooth and colorless. Thus, the roughness and color parameters of Blender's glass shader are ignored during export. There is no external IOR parameter in Blender's glass shader, so it won't be exported either (Nori will use the default value of 1.000277).

### Lights

Only point lights and emission shaders are supported.

### Textures

There is an option to export all textures, but no texture tags are created in the XML since image textures are not a part of Nori's default feature set. You will need to implement this yourself if you need it.

There is limited support for checkerboard textures.

> [!TIP]
> The script automatically generates a relative path to each texture (see the `handle_special_cases` function in `export_materials.py`). If you implement image textures in Nori, you can use that path to load the texture.

### Meshes

> [!IMPORTANT]
> Currently, normals are exported per face vertex (i.e. flat shading). Smooth shading is not supported yet.

## Extending Shader Support

> [!TIP]
> Simple shaders that have a direct mapping between Blender and Nori can be added by modifying the mappings inside the Bento config 'config.yaml'. Go to `Edit > Preferences > Add-ons > Bento` to see the config path.

The config file consists of four mappings used to translate Blender concepts to Nori concepts:

- `node_tag_map`: Maps Blender shader node types to Nori **tags**. Examples:
    - `BSDF_DIFFUSE` -> `bsdf`
    - `BSDF_GLOSSY` -> `bsdf`
    - `TEX_CHECKER` -> `texture`
    - `EMISSION` -> `emitter`
- `node_map`: Maps Blender shader node types to Nori **types**. Examples:
    - `BSDF_DIFFUSE` -> `diffuse`
    - `BSDF_GLOSSY` -> `microfacet`
    - `TEX_CHECKER` -> `checkerboard`
    - `EMISSION` -> `area`
- `parameter_map`: Maps Blender shader node parameters to Nori **parameter names**. Examples:
    - `BSDF_DIFFUSE.Color` -> `albedo`
    - `BSDF_GLASS.IOR` -> `intIOR`
- `type_map`: Maps Blender shader node parameter types to Nori **parameter tags**. Examples:
    - `RGBA` -> `color`
    - `VALUE` -> `float`

Complete example (Diffuse shader):

| Blender                       | Nori                           | Conversion done by |
| ----------------------------- | ------------------------------ | ------------------ |
| BSDF_DIFFUSE (Node type)      | <**bsdf** ...> (tag)               | node_tag_map       |
| BSDF_DIFFUSE (Node type)      | \<bsdf type="**diffuse**" /> (type) | node_map           |
| Color (Diffuse parameter)     | \<color name="**albedo**" /> (name) | parameter_map      |
| RGBA (Blender parameter type) | <**color** ...> (tag)    | type_map           |

![](diffuse_shader.png)

> [!NOTE]
> Many parameters cannot be mapped one-to-one due to differences in how Blender and Nori handle certain concepts. For example, Blender's Glossy shader has a "Roughness" parameter, while Nori's Microfacet shader uses "alpha" (roughness squared). Conversions like this need to be implemented directly in the code (roughness to alpha conversion is already implemented). See the `handle_special_cases` function in `export_materials.py` for more examples. Note that you still need to add the proper mappings to `node_tag_map` and `node_map` for the shader to be recognized. To find out the Blender type of a node, select it in the node tree and then run the following in Blender's Python console: `C.active_object.active_material.node_tree.nodes.active.type`.

## TODO
- Checker texture scaling
- More safety checks (e.g. ensure user is in object mode before exporting)
