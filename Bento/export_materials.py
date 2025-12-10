import bpy
import os
import tomllib
import xml.etree.ElementTree as ET


def load_config(prefs):
    config = {}
    config_path = bpy.path.abspath(prefs.config_path)
    if os.path.exists(config_path):
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

    return (
        config["node_tag_map"],
        config["node_map"],
        config["parameter_map"],
        config["type_map"],
    )


def traverse_material_nodes(material, config, texture_dir, export_settings):
    if not material.use_nodes:
        return

    node_tree = material.node_tree

    output_nodes = [n for n in node_tree.nodes if n.type == "OUTPUT_MATERIAL"]
    if not output_nodes:
        print(f"Material '{material.name}' has no Material Output node.")
        return

    output_node = output_nodes[0]
    shader_node = output_node.inputs["Surface"].links[0].from_node

    visited = set()

    _, _, parameter_map, _ = config

    def traverse(node):
        if node in visited:
            return
        visited.add(node)

        child_tags = []
        for input_socket in node.inputs:
            for link in input_socket.links:
                from_node = link.from_node
                child_tag = traverse(from_node)
                if child_tag is not None:
                    param_name = parameter_map.get(node.type, {}).get(input_socket.name)
                    if param_name:
                        child_tag.set("name", param_name)
                    child_tags.append(child_tag)

        node_tag = node_to_xml(node, config, texture_dir, export_settings)
        if node_tag is None:
            return None

        for child_tag in child_tags:
            node_tag.append(child_tag)

        return node_tag

    node_tree_xml = traverse(shader_node)
    return node_tree_xml


def convert_values(value, param_type):
    if param_type == "color":
        return ",".join([str(round(v, 4)) for i, v in enumerate(value) if i < 3])
    elif param_type == "float":
        # Handle both single floats and array-like objects (e.g., bpy_prop_array)
        if hasattr(value, "__iter__") and not isinstance(value, str):
            # If it's an iterable (but not a string), take the first element
            return str(round(float(value[0]), 4))
        return str(round(float(value), 4))

    return str(value)


def node_to_xml(node, config, texture_dir, export_settings):
    node_tag_map, node_map, parameter_map, type_map = config

    node_type = node_map.get(node.type)
    export_img = node.type == "TEX_IMAGE" and export_settings.export_textures
    if not node_type and not export_img:
        return None

    node_tag = ET.Element(node_tag_map.get(node.type), type=node_type)

    special_tag = handle_special_cases(node, node_tag, texture_dir, export_settings)
    if special_tag is not None:
        return special_tag

    for input_socket in node.inputs:
        if len(input_socket.links) > 0:
            continue

        param_name = parameter_map.get(node.type, {}).get(input_socket.name)
        if not param_name:
            continue

        param_type = type_map.get(input_socket.type)
        param_value = convert_values(input_socket.default_value, param_type)
        ET.SubElement(node_tag, param_type, name=param_name, value=param_value)

    return node_tag


def handle_special_cases(node, node_tag, texture_dir, export_settings):
    match node.type:
        case "EMISSION":
            # We need to multiply color by strength to get radiance
            color = node.inputs.get("Color").default_value
            strength = node.inputs.get("Strength").default_value
            radiance = [c * strength for c in color[:3]]
            ET.SubElement(
                node_tag,
                "color",
                name="radiance",
                value=convert_values(radiance, "color"),
            )
            return node_tag

        case "BSDF_PRINCIPLED":
            # Export Principled BSDF as Disney BSDF
            # Base Color
            base_color = node.inputs.get("Base Color")
            if base_color and len(base_color.links) == 0:
                ET.SubElement(
                    node_tag,
                    "color",
                    name="baseColor",
                    value=convert_values(base_color.default_value, "color"),
                )

            # Subsurface → Subsurface Weight
            subsurface = node.inputs.get("Subsurface Weight")
            if not subsurface:  # Fallback for older Blender versions
                subsurface = node.inputs.get("Subsurface")
            if subsurface and len(subsurface.links) == 0:
                ET.SubElement(
                    node_tag,
                    "float",
                    name="subsurface",
                    value=convert_values(subsurface.default_value, "float"),
                )

            # Metallic
            metallic = node.inputs.get("Metallic")
            if metallic and len(metallic.links) == 0:
                ET.SubElement(
                    node_tag,
                    "float",
                    name="metallic",
                    value=convert_values(metallic.default_value, "float"),
                )

            # Specular IOR Level → Specular
            specular = node.inputs.get("Specular IOR Level")
            if not specular:  # Fallback for older Blender versions
                specular = node.inputs.get("Specular")
            if specular and len(specular.links) == 0:
                ET.SubElement(
                    node_tag,
                    "float",
                    name="specular",
                    value=convert_values(specular.default_value, "float"),
                )

            # Specular Tint
            specular_tint = node.inputs.get("Specular Tint")
            if specular_tint and len(specular_tint.links) == 0:
                ET.SubElement(
                    node_tag,
                    "float",
                    name="specularTint",
                    value=convert_values(specular_tint.default_value, "float"),
                )

            # Roughness
            roughness = node.inputs.get("Roughness")
            if roughness and len(roughness.links) == 0:
                ET.SubElement(
                    node_tag,
                    "float",
                    name="roughness",
                    value=convert_values(roughness.default_value, "float"),
                )

            # Sheen Weight → Sheen
            sheen = node.inputs.get("Sheen Weight")
            if not sheen:  # Fallback for older Blender versions
                sheen = node.inputs.get("Sheen")
            if sheen and len(sheen.links) == 0:
                ET.SubElement(
                    node_tag,
                    "float",
                    name="sheen",
                    value=convert_values(sheen.default_value, "float"),
                )

            # Sheen Tint
            sheen_tint = node.inputs.get("Sheen Tint")
            if sheen_tint and len(sheen_tint.links) == 0:
                ET.SubElement(
                    node_tag,
                    "float",
                    name="sheenTint",
                    value=convert_values(sheen_tint.default_value, "float"),
                )

            # Coat Weight → Clearcoat
            coat = node.inputs.get("Coat Weight")
            if not coat:  # Fallback for older Blender versions
                coat = node.inputs.get("Clearcoat")
            if coat and len(coat.links) == 0:
                ET.SubElement(
                    node_tag,
                    "float",
                    name="clearcoat",
                    value=convert_values(coat.default_value, "float"),
                )

            # Coat Roughness → Clearcoat Gloss (INVERTED!)
            coat_roughness = node.inputs.get("Coat Roughness")
            if not coat_roughness:  # Fallback for older Blender versions
                coat_roughness = node.inputs.get("Clearcoat Roughness")
            if coat_roughness and len(coat_roughness.links) == 0:
                # Invert: clearcoatGloss = 1.0 - coat_roughness
                clearcoat_gloss = 1.0 - coat_roughness.default_value
                ET.SubElement(
                    node_tag,
                    "float",
                    name="clearcoatGloss",
                    value=convert_values(clearcoat_gloss, "float"),
                )

            return node_tag

        case "BSDF_GLOSSY":
            roughness = node.inputs.get("Roughness").default_value
            alpha = roughness**2
            if alpha < 0.00001:
                node_tag = ET.Element("bsdf", type="mirror")
                return node_tag

            ET.SubElement(
                node_tag, "float", name="alpha", value=convert_values(alpha, "float")
            )
            ET.SubElement(node_tag, "color", name="kd", value="0,0,0")
            return node_tag

        case "TEX_IMAGE":
            img_path = export_texture(node, texture_dir, export_settings)
            # You can use 'image_path' directly in the XML
            # It's a relative path, so you can use it just like meshes
            # E.g. "textures/___.png"
            return node_tag

        case _:
            return None


def export_texture(node, texture_dir, export_settings):
    if not export_settings.export_textures:
        return

    img = node.image

    if not img:
        return

    img_name = os.path.splitext(img.name)[0]
    file_ext = export_settings.texture_format.lower()
    out_path = os.path.join(texture_dir, img_name + f".{file_ext}")

    original_format = img.file_format
    img.file_format = export_settings.texture_format

    try:
        # `save()` works for both packed and external images
        img.save(filepath=out_path)
    finally:
        # --- Restore original format ---
        img.file_format = original_format

    print(f"Exported texture to: {out_path}")
    return f"textures/{img_name}.{file_ext}"


def export_materials(config, texture_dir, export_settings):
    materials = {}
    for mat in bpy.data.materials:
        xml = traverse_material_nodes(mat, config, texture_dir, export_settings)
        if xml is not None:
            materials[mat.name] = xml

    return materials
