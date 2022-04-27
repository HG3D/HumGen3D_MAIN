from __future__ import annotations

import os
from pathlib import Path
from typing import List

import bpy
from bpy.types import Context, Material, ShaderNode, bpy_prop_collection

from ...old.blender_backend.preview_collections import refresh_pcoll
from ...old.blender_operators.common.common_functions import (
    ShowMessageBox,
    get_prefs,
)


class SkinSettings:
    def __init__(self, human):
        self._human = human

    @property
    def texture(self) -> TextureSettings:
        if not hasattr(self, "_texture"):
            self._texture = TextureSettings(self._human)
        return self._texture

    @property
    def nodes(self) -> SkinNodes:
        if not hasattr(self, "_nodes"):
            self._nodes = SkinNodes(self._human)
        return self._nodes

    @property
    def links(self) -> SkinLinks:
        if not hasattr(self, "_links"):
            self._links = SkinLinks(self._human)
        return self._links

    @property
    def material(self) -> Material:
        return self._human.body_obj.data.materials[0]

    def _mac_material_fix(self):
        self.links.new(
            self.nodes["Mix_reroute_1"].outputs[0],
            self.nodes["Mix_reroute_2"].inputs[1],
        )

    def _set_gender_specific(self):
        """Male and female humans of HumGen use the same shader, but one node
        group is different. This function ensures the right nodegroup is connected

        Args:
            hg_body (Object)
        """
        gender = self._human.gender
        uw_node = self.nodes.get("Underwear_Switch")

        if uw_node:
            uw_node.inputs[0].default_value = 1 if gender == "female" else 0

        if gender == "male":
            gender_specific_node = self.nodes["Gender_Group"]
            male_node_group = [
                ng
                for ng in bpy.data.node_groups
                if ".HG_Beard_Shadow" in ng.name
            ][0]
            gender_specific_node.node_tree = male_node_group

    def _remove_opposite_gender_specific(self):
        self.nodes.remove(self.nodes.get("Delete_node"))

    def _set_from_preset(self, preset_data: dict):
        for node_name, input_dict in preset_data.items():
            node = self.nodes.get(node_name)

            for input_name, value in input_dict.items():
                if input_name.isnumeric():
                    input_name = int(input_name)
                node.inputs[input_name].default_value = value


class TextureSettings:
    def __init__(self, human):
        self._human = human

    def set(self, textureset_path: str, context: Context = None):
        if not context:
            context = bpy.context
        diffuse_texture = textureset_path
        library = "Default 4K"  # TODO

        if diffuse_texture == "none":
            return

        nodes = self._human.skin.nodes
        gender = self._human.gender

        self._add_texture_to_node(nodes.get("Color"), diffuse_texture, "Color")

        for node in nodes.get_image_nodes():
            for tx_type in ["skin_rough_spec", "Normal"]:
                if tx_type in node.name:
                    pbr_path = os.path.join("textures", gender, library, "PBR")
                    self._add_texture_to_node(node, pbr_path, tx_type)

        if library in ["Default 1K", "Default 512px"]:
            resolution_folder = (
                "MEDIUM_RES" if library == "Default 1K" else "LOW_RES"
            )
            self._change_peripheral_texture_resolution(resolution_folder)

        self._human.skin.material["texture_library"] = library

    def _set_from_preset(self, mat_preset_data, context=None):
        if not context:
            context = bpy.context

        refresh_pcoll(None, context, "textures")

        texture_name = mat_preset_data["diffuse"]
        texture_library = mat_preset_data["texture_library"]
        gender = self._human.gender

        self.set(
            os.path.join("textures", gender, texture_library, texture_name)
        )

    def _change_peripheral_texture_resolution(
        self, resolution_folder, hg_rig, hg_body
    ):
        # TODO cleanup
        for obj in hg_rig.children:
            for mat in obj.data.materials:
                for node in [
                    node
                    for node in mat.node_tree.nodes
                    if node.bl_idname == "ShaderNodeTexImage"
                ]:
                    if (
                        node.name.startswith(
                            ("skin_rough_spec", "Normal", "Color")
                        )
                        and obj == hg_body
                    ):
                        continue
                    current_image = node.image
                    current_path = current_image.filepath

                    if (
                        "MEDIUM_RES" in current_path
                        or "LOW_RES" in current_path
                    ):
                        current_dir = Path(
                            os.path.dirname(current_path)
                        ).parent
                    else:
                        current_dir = os.path.dirname(current_path)

                    dir = os.path.join(current_dir, resolution_folder)
                    fn, ext = os.path.splitext(os.path.basename(current_path))
                    resolution_tag = resolution_folder.replace("_RES", "")
                    corrected_fn = (
                        fn.replace("_4K", "")
                        .replace("_MEDIUM", "")
                        .replace("_LOW", "")
                        .replace("_2K", "")
                    )
                    new_fn = corrected_fn + f"_{resolution_tag}" + ext
                    new_path = os.path.join(dir, new_fn)

                    old_color_mode = current_image.colorspace_settings.name
                    node.image = bpy.data.images.load(
                        new_path, check_existing=True
                    )
                    node.image.colorspace_settings.name = old_color_mode

    def _add_texture_to_node(self, node, sub_path, tx_type):
        """Adds correct image to the teximage node

        Args:
            node      (ShaderNode): TexImage node to add image to
            sub_path  (Path)      : Path relative to HumGen folder where the texture
                                is located
            tx_type   (str)       : what kind of texture it is (Diffuse, Roughness etc.)
        """
        pref = get_prefs()

        filepath = os.path.join(pref.filepath, sub_path)

        # TODO cleanup

        if tx_type == "Color":
            image_path = filepath
        else:
            if tx_type == "Normal":
                tx_type = "norm"
            for fn in os.listdir(filepath):
                if tx_type.lower() in fn.lower():
                    image_path = os.path.join(filepath, fn)

        image = bpy.data.images.load(image_path, check_existing=True)
        node.image = image
        if tx_type != "Color":
            if pref.nc_colorspace_name:
                image.colorspace_settings.name = pref.nc_colorspace_name
                return
            found = False
            for color_space in [
                "Non-Color",
                "Non-Colour Data",
                "Utility - Raw",
            ]:
                try:
                    image.colorspace_settings.name = color_space
                    found = True
                    break
                except TypeError:
                    pass
            if not found:
                ShowMessageBox(
                    message="Could not find colorspace alternative for non-color data, default colorspace used"
                )


class SkinNodes(bpy_prop_collection):
    def __new__(cls, human):
        skin_mat = human.body_obj.data.materials[0]
        nodes = skin_mat.node_tree.nodes
        return super().__new__(cls, nodes)

    def get_image_nodes(self) -> List[ShaderNode]:
        return [
            node for node in self if node.bl_idname == "ShaderNodeTexImage"
        ]


class SkinLinks(bpy_prop_collection):
    def __new__(cls, human):
        skin_mat = human.body_obj.data.materials[0]
        links = skin_mat.node_tree.links
        return super().__new__(cls, links)