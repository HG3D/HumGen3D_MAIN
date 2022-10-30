import contextlib
import json
import os
import random
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Iterable, Literal, Set

import bmesh
import bpy
import numpy as np
from HumGen3D import get_prefs
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.geometry import obj_from_pydata  # noqa
from HumGen3D.common.math import create_kdtree, normalize
from HumGen3D.common.memory_management import hg_delete
from HumGen3D.common.shapekey_calculator import (
    build_distance_dict,
    deform_obj_from_difference,
    world_coords_from_obj,
)
from HumGen3D.common.type_aliases import C
from HumGen3D.extern.rdp import rdp

if TYPE_CHECKING:
    from ..human import Human

UVCoords = list[list[list[float]]]


class HairCollection:
    def __init__(
        self,
        hair_obj: bpy.types.Object,
        human: "Human",
    ) -> None:
        self.mx_world_hair_obj = hair_obj.matrix_world

        body_world_coords_eval = world_coords_from_obj(
            human.body_obj, data=human.keys.all_deformation_shapekeys
        )
        self.kd = create_kdtree(body_world_coords_eval)

        self.hair_coords = world_coords_from_obj(hair_obj)
        nearest_vert_idx = np.array([self.kd.find(co)[1] for co in self.hair_coords])
        verts = human.body_obj.data.vertices
        self.nearest_normals = np.array(
            [tuple(verts[idx].normal.normalized()) for idx in nearest_vert_idx]
        )

        bm = bmesh.new()  # type:ignore[call-arg]
        bm.from_mesh(hair_obj.data)
        self.hairs = list(self._get_individual_hairs(bm))
        bm.free()
        hg_delete(hair_obj)
        self.objects: dict[int, bpy.types.Object] = {}

    @staticmethod
    def _walk_island(vert: bmesh.types.BMVert) -> Iterable[int]:
        """walk all un-tagged linked verts"""
        vert.tag = True
        yield vert.index
        linked_verts = [
            e.other_vert(vert) for e in vert.link_edges if not e.other_vert(vert).tag
        ]

        for v in linked_verts:
            if v.tag:
                continue
            yield from HairCollection._walk_island(v)

    def _get_individual_hairs(
        self, bm: bmesh.types.BMesh
    ) -> Iterable[tuple[np.ndarray[Any, Any], float]]:  # noqa[TAE002]

        start_verts = []
        for v in bm.verts:
            if len(v.link_edges) == 1:
                start_verts.append(v)
        islands_dict: dict[int, list[np.ndarray[Any, Any]]] = defaultdict()  # noqa

        found_verts = set()
        for start_vert in start_verts:
            if start_vert.index in found_verts:
                continue
            island_idxs = np.fromiter(self._walk_island(start_vert), dtype=np.int64)

            yield island_idxs, np.linalg.norm(
                self.hair_coords[island_idxs[0]] - self.hair_coords[island_idxs[-2]]
            )

            found_verts.add(island_idxs[-1])

    def create_mesh(
        self, quality: Literal["low", "medium", "high", "ultra"] = "high"
    ) -> Iterable[bpy.types.Object]:

        long_hairs = [hair for hair, length in self.hairs if length > 0.1]
        medium_hairs = [hair for hair, length in self.hairs if 0.1 >= length > 0.05]
        short_hairs = [hair for hair, length in self.hairs if 0.05 >= length]

        quality_dict = {
            "ultra": (1, 5, 6, 0.002, 0.5),
            "high": (3, 6, 6, 0.003, 1),
            "medium": (6, 12, 14, 0.005, 1),
            "low": (15, 20, 20, 0.005, 2),
        }
        chosen_quality = quality_dict[quality]

        all_hairs = []
        for i, hair_list in enumerate((short_hairs, medium_hairs, long_hairs)):
            if len(hair_list) > 30:
                all_hairs.extend(hair_list[:: chosen_quality[i]])
            else:
                all_hairs.extend(hair_list)

        rdp_downsized_hair_co_idxs = [
            hair_vert_idxs[
                rdp(
                    self.hair_coords[hair_vert_idxs],
                    epsilon=chosen_quality[3],
                    return_mask=True,
                )
            ]
            for hair_vert_idxs in all_hairs
        ]
        hair_len_dict: dict[int, list[list[int]]] = defaultdict()  # noqa[TAE002]
        for hair_vert_idxs in rdp_downsized_hair_co_idxs:
            hair_len_dict.setdefault(len(hair_vert_idxs), []).append(hair_vert_idxs)

        hair_len_dict_np: dict[int, np.ndarray[Any, Any]] = {
            i: np.array(hairs) for i, hairs in hair_len_dict.items()
        }

        for hair_co_len, hair_vert_idxs in hair_len_dict_np.items():
            hair_coords = self.hair_coords[hair_vert_idxs]
            nearest_normals = self.nearest_normals[hair_vert_idxs]

            perpendicular = self._calculate_perpendicular_vec(
                hair_co_len, hair_coords, nearest_normals
            )

            new_verts, new_verts_parallel = self._compute_new_ver_coordinaes(
                hair_co_len, hair_coords, nearest_normals, perpendicular
            )

            faces, faces_parallel = self._compute_new_face_vert_idxs(
                hair_co_len, hair_coords
            )

            all_verts = np.concatenate((new_verts, new_verts_parallel))
            all_faces = np.concatenate((faces, faces_parallel + len(new_verts)))
            all_faces = all_faces.reshape((-1, 4))

            obj = obj_from_pydata(
                f"hair_{hair_co_len}",
                all_verts,
                faces=all_faces,
                use_smooth=True,
                context=bpy.context,
            )

            self.objects[hair_co_len] = obj
            yield obj

    @staticmethod
    def _create_obj_from_verts_and_faces(
        obj_name: str, all_verts: np.ndarray[Any, Any], all_faces: np.ndarray[Any, Any]
    ) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(name="hair")
        all_verts_as_tuples = [tuple(co) for co in all_verts]
        all_faces_as_tuples = [tuple(idxs) for idxs in all_faces]

        mesh.from_pydata(all_verts_as_tuples, [], all_faces_as_tuples)
        mesh.update()

        for f in mesh.polygons:
            f.use_smooth = True

        obj = bpy.data.objects.new(obj_name, mesh)  # type:ignore[arg-type]
        return obj

    @staticmethod
    def _compute_new_face_vert_idxs(
        hair_co_len: int, hair_coords: np.ndarray[Any, Any]
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        faces = np.empty((len(hair_coords), hair_co_len - 1, 4), dtype=np.int64)

        for i in range(hair_coords.shape[0]):
            for j in range(hair_co_len - 1):
                corr = i * hair_co_len * 2
                faces[i, j, :] = (
                    corr + j,
                    corr + j + 1,
                    corr + hair_co_len * 2 - j - 2,
                    corr + hair_co_len * 2 - j - 1,
                )
        faces_parallel = faces.copy()
        return faces, faces_parallel

    @staticmethod
    def _compute_new_ver_coordinaes(
        hair_co_len: int,
        hair_coords: np.ndarray[Any, Any],
        nearest_normals: np.ndarray[Any, Any],
        perpendicular: np.ndarray[Any, Any],
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        segment_correction = HairCollection._calculate_segment_correction(hair_co_len)
        hair_length = np.linalg.norm(hair_coords[:, 0] - hair_coords[:, -1], axis=1)
        length_correction = np.ones(hair_coords.shape[0])
        np.place(length_correction, hair_length < 0.01, 0.8)
        np.place(length_correction, hair_length < 0.005, 0.6)
        length_correction = length_correction[:, None, None]
        perpendicular_offset = segment_correction * perpendicular * length_correction

        head_normal_offset = (
            segment_correction * np.abs(nearest_normals) * length_correction * 0.3
        )

        hair_coords_right = hair_coords + perpendicular_offset
        hair_coords_left = np.flip(hair_coords, axis=1) - perpendicular_offset
        hair_coords_top = hair_coords + head_normal_offset  # noqa
        hair_coords_bottom = hair_coords - head_normal_offset  # noqa

        new_verts = np.concatenate((hair_coords_left, hair_coords_right), axis=1)
        new_verts_parallel = np.concatenate(
            (hair_coords_top, hair_coords_bottom), axis=1
        )

        new_verts = new_verts.reshape((-1, 3))
        new_verts_parallel = new_verts_parallel.reshape((-1, 3))
        return new_verts, new_verts_parallel

    @staticmethod
    def _calculate_perpendicular_vec(
        hair_co_len: int,
        hair_coords: np.ndarray[Any, Any],
        nearest_normals: np.ndarray[Any, Any],
    ) -> np.ndarray[Any, Any]:
        hair_keys_next_coords = np.roll(hair_coords, -1, axis=1)
        hair_key_vectors = normalize(hair_keys_next_coords - hair_coords)
        if hair_co_len > 1:
            hair_key_vectors[:, -1] = hair_key_vectors[:, -2]

        # Fix for bug in Numpy returning NoReturn causing unreachable code
        def crossf(a: np.ndarray, b: np.ndarray, axis) -> np.ndarray:  # type: ignore
            return np.cross(a, b, axis=axis)

        perpendicular = crossf(nearest_normals, hair_key_vectors, 2)
        return perpendicular

    @staticmethod
    def _calculate_segment_correction(hair_co_len: int) -> np.ndarray[Any, Any]:
        """Makes an array of scalars to make the hair get narrower with each segment."""
        length_correction = np.arange(0.01, 0.03, 0.02 / hair_co_len, dtype=np.float32)

        length_correction = length_correction[::-1]
        length_correction = np.expand_dims(length_correction, axis=-1)
        return length_correction

    def add_uvs(self) -> None:
        haircard_json = os.path.join(
            get_prefs().filepath,
            "hair",
            "haircards",
            "HairMediumLength_zones.json",
        )
        with open(haircard_json, "r") as f:
            hairzone_uv_dict = json.load(f)

        for vert_len, obj in self.objects.items():
            uv_layer = obj.data.uv_layers.new()

            if not obj.data.polygons:
                continue

            vert_loop_dict = self._create_vert_loop_dict(obj, uv_layer)

            self._set_vert_group_uvs(hairzone_uv_dict, vert_len, obj, vert_loop_dict)

    @staticmethod
    def _create_vert_loop_dict(
        obj: bpy.types.Object, uv_layer: bpy.types.MeshUVLoopLayer
    ) -> dict[int, list[bpy.types.MeshUVLoop]]:
        vert_loop_dict: dict[int, list[bpy.types.MeshUVLoop]] = {}

        for poly in obj.data.polygons:
            for vert_idx, loop_idx in zip(poly.vertices, poly.loop_indices):
                loop = uv_layer.data[loop_idx]  # type:ignore
                if vert_idx not in vert_loop_dict:
                    vert_loop_dict[vert_idx] = [
                        loop,
                    ]
                else:
                    vert_loop_dict[vert_idx].append(loop)
        return vert_loop_dict

    @staticmethod
    def _set_vert_group_uvs(
        hairzone_uv_dict: dict[str, dict[str, dict[str, UVCoords]]],  # noqa
        vert_len: int,
        obj: bpy.types.Object,
        vert_loop_dict: dict[int, list[bpy.types.MeshUVLoop]],
    ) -> None:
        verts = obj.data.vertices
        for i in range(0, len(verts), vert_len * 2):
            vert_count = vert_len * 2
            hair_verts = verts[i : i + vert_count]  # noqa

            vert_pairs = []
            for vert in hair_verts[:vert_len]:
                vert_pairs.append((vert.index, vert_count - vert.index - 1))

            vert_pairs = zip(  # type:ignore
                [v.index for v in hair_verts[:vert_len]],
                list(reversed([v.index for v in hair_verts[vert_len:]])),
            )

            length = (hair_verts[0].co - hair_verts[vert_len].co).length
            width = (hair_verts[0].co - hair_verts[-1].co).length
            if length > 0.05:
                subdict = random.choice(list(hairzone_uv_dict["long"].values()))
                if width > 0.02:
                    chosen_zone = random.choice(subdict["wide"])
                else:
                    chosen_zone = random.choice(subdict["narrow"])
            else:
                subdict = random.choice(list(hairzone_uv_dict["short"].values()))
                if width > 0.01:
                    chosen_zone = random.choice(subdict["wide"])
                else:
                    chosen_zone = random.choice(subdict["narrow"])

            bottom_left, top_right = chosen_zone

            for i, (vert_left, vert_right) in enumerate(vert_pairs):
                left_loops = vert_loop_dict[vert_left]
                right_loops = vert_loop_dict[vert_right]

                x_min = bottom_left[0]
                x_max = top_right[0]

                y_min = bottom_left[1]
                y_max = top_right[1]
                y_diff = y_max - y_min

                y_relative = i / (vert_len - 1)
                for loop in left_loops:
                    loop.uv = (x_max, y_min + y_diff * y_relative)

                for loop in right_loops:
                    loop.uv = (x_min, y_min + y_diff * y_relative)

    def add_material(self) -> None:
        mat = bpy.data.materials.get("HG_Haircards")
        if not mat:
            blendpath = os.path.join(
                get_prefs().filepath, "hair", "haircards", "haircards_material.blend"
            )
            with bpy.data.libraries.load(blendpath, link=False) as (
                _,
                data_to,
            ):
                data_to.materials = ["HG_Haircards"]

            mat = data_to.materials[0]
        else:
            mat = mat.copy()

        self.material = mat

        for obj in self.objects.values():
            obj.data.materials.append(mat)

    @injected_context
    def add_haircap(
        self,
        human: "Human",
        density_vertex_groups: list[bpy.types.VertexGroup],
        context: C = None,
    ) -> bpy.types.Object:
        body_obj = human.body_obj
        vert_count = len(body_obj.data.vertices)

        vg_aggregate = np.zeros(vert_count, dtype=np.float32)

        for vg in density_vertex_groups:
            vg_values = np.zeros(vert_count, dtype=np.float32)
            for i in range(vert_count):
                with contextlib.suppress(RuntimeError):
                    vg_values[i] = vg.weight(i)
            vg_aggregate += vg_values

        vg_aggregate = np.round(vg_aggregate, 4)
        vg_aggregate = np.clip(vg_aggregate, 0, 1)

        blendfile = os.path.join(
            get_prefs().filepath, "hair", "haircards", "haircap.blend"
        )
        with bpy.data.libraries.load(blendfile, link=False) as (_, data_to):
            data_to.objects = [
                "HG_Haircap",
            ]

        haircap_obj = data_to.objects[0]
        context.scene.collection.objects.link(haircap_obj)
        haircap_obj.location = human.location
        body_obj_eval_coords = world_coords_from_obj(
            human.body_obj, data=human.keys.all_deformation_shapekeys
        )
        body_world_coords = world_coords_from_obj(human.body_obj)
        haircap_world_coords = world_coords_from_obj(haircap_obj)
        distance_dict = build_distance_dict(body_world_coords, haircap_world_coords)
        deform_obj_from_difference(
            "test", distance_dict, body_obj_eval_coords, haircap_obj, as_shapekey=False
        )
        vc = haircap_obj.data.color_attributes[0]

        for i, vert_world_co in enumerate(haircap_world_coords):
            nearest_vert_index = self.kd.find(vert_world_co)[1]
            value = vg_aggregate[nearest_vert_index]
            vc.data[i].color = (value, value, value, 1)

        bm = bmesh.new()  # type:ignore[call-arg]
        bm.from_mesh(haircap_obj.data)
        for edge in bm.edges:
            if edge.is_boundary:
                v1, v2 = edge.verts
                vc.data[v1.index].color = (0, 0, 0, 1)
                vc.data[v2.index].color = (0, 0, 0, 1)

        self.haircap_obj = haircap_obj

        return haircap_obj

    def set_node_values(self, human: "Human") -> None:
        card_material = self.material

        cap_material = (
            self.haircap_obj.data.materials[0] if hasattr(self, "haircap_obj") else None
        )

        old_hair_mat = human.body_obj.data.materials[2]
        old_node = next(
            node
            for node in old_hair_mat.node_tree.nodes
            if node.bl_idname == "ShaderNodeGroup"
        )

        for mat in (card_material, cap_material):
            if not mat:
                continue
            node = next(
                node
                for node in mat.node_tree.nodes
                if node.bl_idname == "ShaderNodeGroup"
            )
            for inp_name in ("Lightness", "Redness"):
                node.inputs[inp_name].default_value = old_node.inputs[
                    inp_name
                ].default_value


def expand_region(
    obj: bpy.types.Object, vert_idxs: np.ndarray[Any, Any]
) -> np.ndarray[Any, Any]:
    bm = bmesh.new()  # type:ignore
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    other_verts: Set[int] = set()
    for vert_idx in vert_idxs:
        v = bm.verts[vert_idx]  # type:ignore[index]
        other_verts.update((e.other_vert(v).index for e in v.link_edges))

    with_added_verts = np.append(vert_idxs, list(other_verts))
    return np.unique(with_added_verts)
