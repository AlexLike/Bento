import bpy
import os
import struct
from typing import List, Tuple, Optional


def export_curves(context, directory) -> List[Tuple[str, str, Optional[str]]]:
    """
    Export Blender curves to .HAIR format.

    Returns a list of tuples: (object_name, hair_filename, material_name)
    """
    curves_dir = os.path.join(directory, "curves")
    os.makedirs(curves_dir, exist_ok=True)

    depsgraph = context.evaluated_depsgraph_get()
    curve_data = []

    for obj in context.scene.objects:
        if obj.type != "CURVES":
            continue

        # Skip objects not visible to camera in the outliner
        if obj.hide_render:
            continue

        # Get evaluated object (with modifiers applied)
        eval_obj = obj.evaluated_get(depsgraph)

        # Get the evaluated curves data
        if hasattr(eval_obj, "data") and hasattr(eval_obj.data, "curves"):
            curves = eval_obj.data

            # Check if the object has materials
            materials = curves.materials
            if not materials:
                # Export without material
                filename = export_hair_file(
                    curves, obj.name, obj.matrix_world, curves_dir
                )
                if filename:
                    curve_data.append((obj.name, filename, None))
            else:
                # Export once for each material
                for mat in materials:
                    mat_name = mat.name if mat else "default"
                    full_name = f"{obj.name}_{mat_name}"
                    filename = export_hair_file(
                        curves, full_name, obj.matrix_world, curves_dir
                    )
                    if filename:
                        curve_data.append((full_name, filename, mat_name))

    return curve_data


def export_hair_file(curves, obj_name, transform_matrix, output_dir) -> Optional[str]:
    """
    Export curves data to .HAIR binary format.

    Args:
        curves: Blender curves data
        obj_name: Name for the output file
        transform_matrix: World transformation matrix
        output_dir: Directory to save the file

    Returns:
        Filename (without directory) if successful, None otherwise
    """

    # Access the curves
    if not hasattr(curves, "curves") or len(curves.curves) == 0:
        print(f"Warning: Object '{obj_name}' has no curve data")
        return None

    num_strands = len(curves.curves)

    # Collect strand information
    segments_array = []
    points_array = []
    thickness_array = []

    total_points = 0

    # Iterate through each curve/strand
    for curve_idx in range(num_strands):
        curve = curves.curves[curve_idx]

        # Get the point range for this curve
        first_point = curve.first_point_index
        num_points = curve.points_length

        # Number of segments = number of points - 1
        num_segments = max(0, num_points - 1)
        segments_array.append(num_segments)

        # Extract points for this curve
        for point_idx in range(first_point, first_point + num_points):
            # Get point position
            point_pos = curves.points[point_idx].position

            # Transform to world space
            world_pos = transform_matrix @ point_pos

            # Add to points array (x, y, z)
            points_array.extend([world_pos.x, world_pos.y, world_pos.z])

            # Get radius/thickness for this point
            # Blender stores radius, but .HAIR expects thickness (diameter = 2 * radius)
            if hasattr(curves.points[point_idx], "radius"):
                radius = curves.points[point_idx].radius
                thickness = radius * 2.0
            else:
                # Default thickness if radius is not available
                thickness = 0.01

            thickness_array.append(thickness)
            total_points += 1

    if total_points == 0:
        print(f"Warning: Object '{obj_name}' has no points")
        return None

    # Prepare header
    magic = b"HAIR"

    # Bit flags for what data is included
    # Bit 0: segments array (1)
    # Bit 1: points array (1) - required
    # Bit 2: thickness array (1)
    # Bit 3: transparency array (0)
    # Bit 4: color array (0)
    bit_flags = 0b00000111  # segments, points, and thickness

    # Default values (used when arrays are not present)
    default_segments = 0  # Not used since we include segments array
    default_thickness = 0.01
    default_transparency = 0.0
    default_color = [1.0, 1.0, 1.0]  # White

    # File information string (max 88 bytes)
    file_info = f"Exported from Blender {bpy.app.version_string}".encode("ascii")
    file_info = file_info[:88].ljust(88, b"\x00")  # Pad or truncate to 88 bytes

    # Write the .HAIR file
    filename = f"{obj_name}.hair"
    filepath = os.path.join(output_dir, filename)

    try:
        with open(filepath, "wb") as f:
            # Header (128 bytes)
            f.write(magic)  # Bytes 0-3
            f.write(struct.pack("I", num_strands))  # Bytes 4-7: number of strands
            f.write(struct.pack("I", total_points))  # Bytes 8-11: total points
            f.write(struct.pack("I", bit_flags))  # Bytes 12-15: bit flags
            f.write(struct.pack("I", default_segments))  # Bytes 16-19: default segments
            f.write(
                struct.pack("f", default_thickness)
            )  # Bytes 20-23: default thickness
            f.write(
                struct.pack("f", default_transparency)
            )  # Bytes 24-27: default transparency
            f.write(
                struct.pack("fff", *default_color)
            )  # Bytes 28-39: default color (3 floats)
            f.write(file_info)  # Bytes 40-127: file info (88 bytes)

            # Segments array (unsigned short for each strand)
            for seg_count in segments_array:
                f.write(struct.pack("H", seg_count))  # Unsigned short (2 bytes)

            # Points array (float x 3 for each point)
            for coord in points_array:
                f.write(struct.pack("f", coord))  # Float (4 bytes)

            # Thickness array (float for each point)
            for thickness in thickness_array:
                f.write(struct.pack("f", thickness))  # Float (4 bytes)

        print(f"Exported curves '{obj_name}' to {filepath}")
        return filename

    except Exception as e:
        print(f"Error exporting curves '{obj_name}': {e}")
        return None
