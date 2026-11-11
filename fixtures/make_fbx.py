"""Builds the lotus test FBX files used by the Unity tests and the test Prism project.

Run with Blender 4.5:
    blender -b --factory-startup -P fixtures/make_fbx.py -- <output folder>

lotus_v1.fbx          Lotus/{Petals, Stem}, materials PetalMat, StemMat
lotus_v2.fbx          same names, Petals scaled by 10%
lotus_v3_renamed.fbx  Stem renamed to StemMain, StemMat removed (breaking update)
cay_v1.fbx            a single "Cup" mesh with material CupMat
"""

import os
import sys

import bpy


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    return mat


def mesh_object(name, kind, parent=None, mat=None, scale=1.0, location=(0, 0, 0)):
    if kind == "petals":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.5 * scale, location=location)
    elif kind == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.08, depth=1.0, location=location)
    else:
        bpy.ops.mesh.primitive_cube_add(size=0.4 * scale, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name + "Mesh"
    if mat is not None:
        obj.data.materials.clear()
        obj.data.materials.append(material(mat))
    if parent is not None:
        obj.parent = parent
    return obj


def root(name):
    bpy.ops.object.empty_add(type="PLAIN_AXES")
    obj = bpy.context.active_object
    obj.name = name
    return obj


def export(path):
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=False,
        apply_unit_scale=True,
        bake_space_transform=False,
        object_types={"EMPTY", "MESH"},
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
        path_mode="STRIP",
    )


def build_lotus(out, filename, petal_scale=1.0, stem_name="Stem", stem_mat="StemMat"):
    reset()
    lotus = root("Lotus")
    mesh_object("Petals", "petals", lotus, "PetalMat", scale=petal_scale, location=(0, 0, 1.0))
    mesh_object(stem_name, "cylinder", lotus, stem_mat, location=(0, 0, 0.5))
    export(os.path.join(out, filename))


def build_cup(out):
    reset()
    mesh_object("Cup", "cube", None, "CupMat")
    export(os.path.join(out, "cay_v1.fbx"))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[0] if argv else os.path.dirname(__file__))
    os.makedirs(out, exist_ok=True)
    build_lotus(out, "lotus_v1.fbx")
    build_lotus(out, "lotus_v2.fbx", petal_scale=1.1)
    build_lotus(out, "lotus_v3_renamed.fbx", stem_name="StemMain", stem_mat=None)
    build_cup(out)
    print("fixtures written to", out)


main()
