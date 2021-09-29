"""
This file is currently inactive
"""

from .. features.batch_section.HG_BATCH_OPS import get_batch_marker_list
import bpy #type: ignore
from .. core.HG_PCOLL import preview_collections
from . HG_PANEL_FUNCTIONS import get_flow, draw_panel_switch_header

class Batch_PT_Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    def Header (self, context):
        return True

class HG_PT_BATCH_Panel(Batch_PT_Base, bpy.types.Panel):
    bl_idname = "HG_PT_Batch_Panel"
    bl_label = "Batch Mode" #tab name

    @classmethod
    def poll(cls, context):
        return context.scene.HG3D.active_ui_tab == 'BATCH'
    
    def draw_header(self, context):
        draw_panel_switch_header(self.layout, context.scene.HG3D)

    def draw(self,context):
        layout=self.layout
        sett = context.scene.HG3D

        col = layout.column(align = True)
        col.scale_y = 1.5
        col.prop(sett, 'batch_marker_selection', text = '')
        
        marker_total = len(get_batch_marker_list(context))
        
        col = col.column(align = True)
        col.alert = True
        col.operator('hg3d.generate', text = f'Generate {marker_total} humans', depress = True, icon  = 'TIME').run_immediately = False

        if sett.batch_idx:
            col = layout.column(align = True)
            col.scale_y = 2
            col.prop(sett, 'batch_progress')

class HG_PT_B_GENERATION_PROBABILITY(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = "Generation Probability"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        if not self.Header(context):
            return
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D

        col = layout.column(align = True)

        flow = get_flow(sett, col)
        flow.separator() 
        flow.prop(sett, 'male_chance')
        flow.prop(sett, 'female_chance')
        flow.separator()

        flow.prop(sett, 'caucasian_chance')
        flow.prop(sett, 'black_chance')
        flow.prop(sett, 'asian_chance')

class HG_PT_B_QUALITY(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = "Quality"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        if not self.Header(context):
            return
        
    def draw(self, context):
        layout = self.layout
        layout.label(text = 'Delete backup model')
        layout.label(text = 'Texture Resolution')
        layout.label(text = 'No Subdivision')
        layout.label(text = 'Decimate Clothing')
        layout.label(text = 'Decimate Human')
        layout.label(text ='Hair Quality')

class HG_PT_B_HAIR(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = " Hair"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        header(self,context, 'hair')
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        layout.enabled = sett.batch_hair

        row = layout.row(align = True)
        row.scale_y = 1.5
        row.prop(sett, 'batch_hairtype', expand = True)

class HG_PT_B_CLOTHING(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = " Clothing"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        header(self, context,'clothing')

    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        layout.enabled = sett.batch_clothing
        hg_icons = preview_collections['hg_icons']
        
        col = layout.column(align = True)
        box =col.box().row()
        box.label(text = 'Select libraries:')
        box.operator('hg3d.uilists', text = '', icon = 'FILE_REFRESH')

        #col.scale_y = 1.5
        row=col.row(align = False)
        row.template_list("HG_UL_BATCH_CLOTHING", "", context.scene, "batch_outfits_col", context.scene, "batch_outfits_col_index")
        
        col = layout.column()
        count = sum([(item.male_items + item.female_items) for item in context.scene.batch_outfits_col])
        col.label(text = 'Total: {} Outfits'.format(count))
        


class HG_PT_B_EXPRESSION(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = " Expression"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        header(self, context, 'expression')

    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        layout.enabled = sett.batch_expression

        col = layout.column(align = True)
        box =col.box().row()
        box.label(text = 'Select libraries:')
        box.operator('hg3d.uilists', text = '', icon = 'FILE_REFRESH')
        col = col.column()
        col.template_list("HG_UL_BATCH_EXPRESSIONS", "", context.scene, "batch_expressions_col", context.scene, "batch_expressions_col_index")

        count = sum([item.count for item in context.scene.batch_expressions_col])
        col.label(text = 'Total: {} Expressions'.format(count))

def header(self, context, categ):
    sett = context.scene.HG3D
    layout = self.layout
    layout.prop(sett, 'batch_{}'.format(categ), text="")