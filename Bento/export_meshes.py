import bpy
import bmesh
import os
import math
from typing import Optional, Tuple, List
from mathutils import Vector


def is_sphere(mesh, tolerance=0.001) -> Tuple[bool, Optional[Vector], Optional[float]]:
    """Detect if a mesh is a sphere by checking if all vertices are equidistant from center."""
    if len(mesh.vertices) < 20:
        return False, None, None

    # Calculate center as average of all vertices
    center = sum(
        (v.co for v in mesh.vertices), start=mesh.vertices[0].co.copy() * 0
    ) / len(mesh.vertices)

    # Calculate distances from center
    distances = [(v.co - center).length for v in mesh.vertices]

    if not distances:
        return False, None, None

    avg_radius = sum(distances) / len(distances)

    # Check if all distances are within tolerance
    for dist in distances:
        if abs(dist - avg_radius) > tolerance:
            return False, None, None

    # Additional check: bounding box should be roughly cubic
    bbox_min = Vector(
        (
            min(v.co.x for v in mesh.vertices),
            min(v.co.y for v in mesh.vertices),
            min(v.co.z for v in mesh.vertices),
        )
    )
    bbox_max = Vector(
        (
            max(v.co.x for v in mesh.vertices),
            max(v.co.y for v in mesh.vertices),
            max(v.co.z for v in mesh.vertices),
        )
    )
    size = bbox_max - bbox_min

    # Check aspect ratios: all dimensions should be similar
    max_size = max(size)
    min_size = min(size)
    if max_size / min_size > 1.2:  # Allow up to 20% deviation from cubic
        return False, None, None

    # Check if diameter matches radius
    diameter = max_size
    if abs(diameter - 2 * avg_radius) > tolerance * avg_radius * 2:
        return False, None, None

    return True, center, avg_radius


def export_meshes(context, directory) -> List[
    Tuple[
        Optional[str],
        Optional[str],
        Optional[str],
        bool,
        Optional[Vector],
        Optional[float],
    ]
]:
    meshes_dir = os.path.join(directory, "meshes")
    os.makedirs(meshes_dir, exist_ok=True)

    depsgraph = context.evaluated_depsgraph_get()
    mesh_data = []
    for obj in context.scene.objects:
        if obj.type != "MESH":
            continue

        # Skip objects not visible to camera in the outliner
        if obj.hide_render:
            continue

        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        mesh.transform(obj.matrix_world)

        # Check if this is a sphere
        is_spherical, center, radius = is_sphere(mesh)

        materials = mesh.materials

        if not materials or all(m is None for m in materials):
            if is_spherical:
                mesh_data.append((obj.name, None, None, True, center, radius))
            else:
                obj_name, filepath, material, is_sphere_result, center, radius = (
                    export_submesh(mesh, obj.name, directory)
                )
                mesh_data.append(
                    (obj_name, filepath, material, is_sphere_result, center, radius)
                )
        else:
            # Export each non-None material as a separate mesh
            for mat_index, mat in enumerate(materials):
                if mat is None:
                    continue

                if is_spherical:
                    mesh_data.append(
                        (f"{obj.name}_{mat.name}", None, mat.name, True, center, radius)
                    )
                else:
                    obj_name, filepath, material, is_sphere_result, center, radius = (
                        export_material_submesh(
                            mesh, obj.name, mat, mat_index, directory
                        )
                    )
                    mesh_data.append(
                        (obj_name, filepath, material, is_sphere_result, center, radius)
                    )

        eval_obj.to_mesh_clear()
        print(mesh_data)

    return mesh_data


def export_material_submesh(
    mesh, obj_name, material, mat_index, directory
) -> Tuple[
    Optional[str], Optional[str], Optional[str], bool, Optional[Vector], Optional[float]
]:
    """Export only the faces with the given material index, preserving UVs."""
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Get all faces with this material
    faces = [f for f in bm.faces if f.material_index == mat_index]
    if not faces:
        bm.free()
        return None, None, None, False, None, None

    # Create a new bmesh for the submesh
    sub_bm = bmesh.new()

    # Create a mapping from old verts to new verts
    vert_map = {}
    for face in faces:
        for v in face.verts:
            if v not in vert_map:
                vert_map[v] = sub_bm.verts.new(v.co)

    # Copy UV layer if exists
    uv_layer = bm.loops.layers.uv.active
    if uv_layer:
        sub_uv_layer = sub_bm.loops.layers.uv.new(uv_layer.name)
    else:
        sub_uv_layer = None

    # Create faces and copy UVs
    for face in faces:
        new_verts = [vert_map[v] for v in face.verts]
        new_face = sub_bm.faces.new(new_verts)
        new_face.smooth = face.smooth

        for loop_old, loop_new in zip(face.loops, new_face.loops):
            if sub_uv_layer:
                loop_new[sub_uv_layer].uv = loop_old[uv_layer].uv

    # Update mesh and export
    sub_bm.verts.index_update()
    sub_bm.faces.index_update()
    sub_bm.normal_update()

    sub_mesh = bpy.data.meshes.new(f"{obj_name}_{material.name}_mesh")
    sub_bm.to_mesh(sub_mesh)
    sub_bm.free()

    # Temporary object for export
    temp_obj = bpy.data.objects.new(f"{obj_name}_{material.name}", sub_mesh)
    bpy.context.collection.objects.link(temp_obj)

    filepath = os.path.join(directory, f"meshes/{obj_name}_{material.name}.obj")
    bpy.ops.object.select_all(action="DESELECT")
    temp_obj.select_set(True)

    bpy.ops.wm.obj_export(
        filepath=filepath,
        export_selected_objects=True,
        export_materials=False,
        export_uv=True,
        export_normals=True,
        forward_axis="Y",
        up_axis="Z",
    )

    # Cleanup
    bpy.data.objects.remove(temp_obj, do_unlink=True)
    bpy.data.meshes.remove(sub_mesh, do_unlink=True)
    bm.free()

    return (
        f"{obj_name}_{material.name}",
        f"{obj_name}_{material.name}.obj",
        material.name,
        False,
        None,
        None,
    )


def export_submesh(
    mesh, obj_name, directory
) -> Tuple[str, str, None, bool, None, None]:
    """Export mesh without material"""
    mesh_copy = mesh.copy()
    temp_obj = bpy.data.objects.new(obj_name, mesh_copy)
    bpy.context.collection.objects.link(temp_obj)

    filepath = os.path.join(directory, f"meshes/{obj_name}.obj")
    bpy.ops.wm.obj_export(
        filepath=filepath,
        export_selected_objects=True,
        export_materials=True,
        export_uv=True,
        export_normals=True,
        forward_axis="Y",
        up_axis="Z",
    )

    bpy.data.objects.remove(temp_obj, do_unlink=True)
    bpy.data.meshes.remove(mesh_copy, do_unlink=True)

    return obj_name, f"{obj_name}.obj", None, False, None, None
