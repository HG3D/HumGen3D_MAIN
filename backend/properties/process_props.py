import bpy
from bpy.props import BoolProperty, EnumProperty


class ProcessProps(bpy.types.PropertyGroup):
    bake: BoolProperty(default=False)
    modapply_enabled: BoolProperty(default=True)
    human_list_isopen: BoolProperty(default=False)
    output: EnumProperty(
        items=[
            ("replace", "Replace humans", "", 0),
            ("duplicate", "Duplicate humans", "", 1),
            ("export", "Export humans", "", 2),
        ]
    )

    presets: EnumProperty(
        items=[
            ("1", "Bake high res", "", 0),
            ("2", "Unity export", "", 1),
            ("3", "Apply all modifiers", "", 2),
        ]
    )
