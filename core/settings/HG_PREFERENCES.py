""" HumGen add-on preferences and associated functions"""

from ... core.content.HG_CUSTOM_CONTENT_PACKS import build_content_list
from ... features.common.HG_COMMON_FUNC import get_prefs
import bpy #type: ignore
from ... import bl_info
import os
from pathlib import Path
from bpy_extras.io_utils import ImportHelper #type: ignore
from ... core.content.HG_CONTENT_PACKS import cpacks_refresh
from ... core.HG_PCOLL import preview_collections, refresh_pcoll

class HG_PREF(bpy.types.AddonPreferences):
    """ HumGen user preferences """   
    bl_idname = __package__.split('.')[0]

    #RELEASE remove default path
    filepath    : bpy.props.StringProperty(
        name= 'Install Filepath',
        default = r'C:\Users\Ole\OneDrive\HumGen_Files_Main\\'
        )

    latest_version        : bpy.props.IntVectorProperty(default = (0,0,0))
    cpack_update_available: bpy.props.BoolProperty(default = False)
    cpack_update_required : bpy.props.BoolProperty(default = False)

    editing_cpack: bpy.props.StringProperty()

    pref_tabs : bpy.props.EnumProperty(
        name="tabs",
        description="",
        items = [
                ("settings", "Settings",      "", "INFO", 0),
                ("cpacks",   "Content Packs", "", "INFO", 1),
            ],
        default = "settings",
        update = cpacks_refresh
        )   

    custom_content_categ : bpy.props.EnumProperty(
        name="Content type",
        description="",
        items = [
                ("starting_humans", "Starting Humans",  "", 0),
                ("texture_sets",    "Texture sets",     "", 1),
                ("shapekeys",       "Shapekeys",        "", 2),
                ("hairstyles",      "Hairstyles",       "", 3),
                ("poses",           "Poses",            "", 4),
                ("outfits",         "Outfits",          "", 5),
                ("footwear",        "Footwear",         "", 6)    
            ],
        default = "starting_humans"
        )  

    cpack_name: bpy.props.StringProperty()
    cpack_creator: bpy.props.StringProperty()
    cpack_version: bpy.props.IntProperty(min = 0)
    cpack_subversion: bpy.props.IntProperty(min = 0)
    cpack_weblink: bpy.props.StringProperty()

    hide_other_packs: bpy.props.BoolProperty(default = True)

    units : bpy.props.EnumProperty(
        name="units",
        description="",
        items = [
                ("metric",      "Metric",   "", 0),
                ("imperial",    "Imperial", "", 1),
            ],
        default = "metric",
        )   
    hair_section : bpy.props.EnumProperty(
        name="Show hair section",
        description="",
        items = [
                ("both",        "Both phases",          "", 0),
                ("creation",    "Creation phase only",  "", 1),
                ("finalize",    "Finalize phase only",  "", 2),
            ],
        default = "creation",
        )   

    show_confirmation    : bpy.props.BoolProperty(default = True)
    dev_tools : bpy.props.BoolProperty(
        name="Show Dev Tools",
        description="",
        default=True)
    
    auto_hide_hair_switch: bpy.props.BoolProperty(default = True)
    auto_hide_popup : bpy.props.BoolProperty(default = True)
    remove_clothes  : bpy.props.BoolProperty(default = True)
    
    compact_ff_ui : bpy.props.BoolProperty(
        name = 'Compact face UI',
        default = False)
    keep_all_shapekeys : bpy.props.BoolProperty(
        name = 'Keep all shapekeys after creation phase',
        default = False)

    nc_colorspace_name: bpy.props.StringProperty(default = '')
    debug_mode: bpy.props.BoolProperty(default = False)

    def draw(self, context):  
        #check if base content is installed, otherwise show installation ui 
        base_content_found = (
            os.path.exists(
                self.filepath + str(Path('content_packs/Base_Humans.json'))
                ) 
            if self.filepath 
            else False
            )
        if not base_content_found:
            self.first_time_ui(context)
            return
        
        layout = self.layout
        col = layout.column()
        
        if self.editing_cpack:
            self._draw_cpack_editing_ui(layout, context)
            return
                    
        update_statuscode = (
            'cpack_required' if self.cpack_update_required
            else 'addon' if tuple(bl_info['version']) < tuple(self.latest_version) 
            else 'cpack_available' if self.cpack_update_available 
            else None
            ) 
        
        if update_statuscode:
            self._draw_update_notification(col, update_statuscode)
            
        row = col.box().row(align = True)
        row.scale_y = 2
        row.prop(self, 'pref_tabs', expand = True)

        if self.pref_tabs == 'settings':
            self._draw_settings_ui()
        elif self.pref_tabs == 'cpacks':
            self._draw_cpack_ui(context)

    def _draw_update_notification(self, col, update_statuscode):
        """Draws notification if there is an update available

        Args:
            col (UILayout): draw in this
            update_statuscode (str): code showing what kind of update is available
        """
        box = col.box().column(align = True)
            
        row = box.row()
        row.alignment = 'CENTER'
        row.label(text = '*****************************************')
            
        col_h         = box.column()
        col_h.scale_y = 3
        col_h.alert   = update_statuscode == 'cpack_required'
        
        alert_dict = self._get_alert_dict()
        col_h.operator(
            "wm.url_open",
            text=alert_dict[update_statuscode][0],
            icon = alert_dict[update_statuscode][1],
            depress = update_statuscode != 'cpack_required' 
            ).url = 'https://humgen3d.com/support/update'
        
        box.operator(
            "wm.url_open",
            text = 'How to update?',
            icon = 'URL'
            ).url = 'https://humgen3d.com/support/update'
        
        row = box.row()
        row.alignment = 'CENTER'
        row.label(text = '*****************************************')

    def _get_alert_dict(self) -> dict:
        """Dictionary for alert messages and icons for different update status

        Returns:
            dict: 
                key (str): update code
                value (tuple[str, str]):
                    str: message to display
                    str: icon to display
        """
        alert_dict = {
                'cpack_required': [
                    'One or more Content Packs are incompatible and need to be updated!',
                    'ERROR'
                    ],
                'addon': [
                    'A new update of the Human Generator add-on is available!',
                    'INFO'
                    ],
                'cpack_available': [
                    'One or more Content Packs can be updated!',
                    'INFO'
                    ]
            }
            
        return alert_dict
        
    def _draw_settings_ui(self):
        """UI with checkboxes and enums for changing HumGen's preferences"""
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.
        
        col = layout.column(heading="UI:")

        col.prop(self, 'show_confirmation',
                 text = 'Show confirmation popups')
        col.prop(self, 'auto_hide_hair_switch',
                 text = 'Auto hide hair children when switching tabs')
        
        if not self.auto_hide_hair_switch:
            self._draw_warning(
                col, 'Having auto-hide enabled improves viewport performance')
        
        col.prop(self, 'auto_hide_popup',
                 text = 'Show popup when auto-hiding hair')
        col.prop(self, 'compact_ff_ui')
        col.prop(self, 'hair_section',
                 text = 'Show hair section:')

        layout.separator()
        
        col = layout.column(heading="Default behaviour:")        
        col.prop(self, 'remove_clothes',
                 text = 'Remove old clothes when adding new ones')
        col.prop(self, 'keep_all_shapekeys')
        if self.keep_all_shapekeys:
            self._draw_warning(
                col, 'Keeping all shapekeys makes finishing creation phase take longer')
        
        layout.separator()
        
        col = layout.column(heading="Color Profile Compatibility:")
        col.prop(self, 'nc_colorspace_name',
                 text = 'Non-color alternative naming')
        
        layout.separator()
        
        col = layout.column(heading="Advanced options:")
        col.prop(self, 'debug_mode',
                 text = "Debug Mode")
        col.prop(self, 'dev_tools')
        
    def _draw_warning(self, layout, message):
        """Draw a warrning label that's right aligned"""
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text = message, icon = 'ERROR')        

    def _draw_cpack_ui(self, context):
        """UI for the user to check which cpacks are installed, who made them,
        what version they are, what is inside them and a button to delete them
        """
        layout = self.layout
        col = layout.column()
        
        row = col.row()
        row.label(text = 'Install path:')
        
        if self.filepath:
            subrow = row.row()
            subrow.enabled = False
            subrow.prop(self, 'filepath', text = '')
            
        row.operator('hg3d.pathchange', text = 'Change' if self.filepath else 'Select')    

        row = col.row(align = False)
        row.template_list(
            "HG_UL_CONTENTPACKS",
            "",
            context.scene,
            "contentpacks_col",
            context.scene,
            "contentpacks_col_index",
            rows=10
            )
        
        col_side = row.column(align = False)
        col_side.operator('hg3d.cpacksrefresh',
                          icon = 'FILE_REFRESH',
                          text = '')
        col_side.popover(panel='HG_ICON_LEGEND',
                         text = '',
                         icon = 'PRESET')

        box = col.box()
        box.label(text = 'Select packs to install:')
        
        selected_packs = (True if len(context.scene.installpacks_col) != 0 
                          else False)
        
        if selected_packs:
            row = box.row()
            row.template_list(
                "HG_UL_INSTALLPACKS",
                "",
                context.scene,
                "installpacks_col",
                context.scene,
                "installpacks_col_index"
                )
            row.operator('hg3d.removeipack', icon = 'TRASH')
        
        row = box.row()
        row.scale_y = 1.5
        row.operator('hg3d.cpackselect',
                     text = 'Select Content Packs',
                     depress = False if selected_packs else True,
                     icon = 'PACKAGE'
                     )
        
        if selected_packs:
            box = col.box()
            box.label(text = 'Install selected packs')
            
            row = box.row()
            row.scale_y = 1.5
            row.operator('hg3d.cpackinstall',
                         text = 'Install Selected Content Packs',
                         depress =True,
                         icon = 'PACKAGE'
                         )

        box = layout.box()
        box.scale_y = 1.5
        box.label(text = 'Create your own content pack:')
        row = box.row()
        row.prop(self, "cpack_name", text = 'Pack name')
        row.operator('hg3d.create_cpack', text = 'Create pack', depress = True)

    def first_time_ui(self, context):
        """UI for when no base humans can be found, promting the user to install
        the content packs"""
        layout = self.layout
        
        #tutorial link section
        box         = layout.box()
        box.scale_y = 1.5
        box.label(text = 'STEP 1: Follow the installation tutorial')
        
        row       = box.row()
        row.alert = True
        row.operator("wm.url_open",
                     text = 'Installation tutorial [Opens browser]',
                     icon= 'HELP',
                     depress = True
                     ).url = 'https://www.humgen3d.com/install'

        #select path section
        box = layout.box()
        box.scale_y = 1.5
        box.label(
            text = "STEP 2: Select a folder for HumGen to install content packs in. 2 GB free space recommended.")
        
        if self.filepath:
            d_row = box.row()
            d_row.enabled = False
            d_row.prop(self, 'filepath', text = '')
        
        box.operator(
            'hg3d.pathchange',
            text = 'Change folder' if self.filepath else 'Select folder',
            depress = False if self.filepath else True,
            icon = 'FILEBROWSER')
        box.label(
            text = "If you've already installed content packs, just select that folder.",
            icon = 'INFO')

        if not self.filepath:
            return
        
        #select packs section
        box = layout.box()
        box.label(text = 'STEP 3: Select packs to install')
        
        row = box.row()
        row.template_list(
            "HG_UL_INSTALLPACKS",
            "",
            context.scene,
            "installpacks_col",
            context.scene,
            "installpacks_col_index"
            )
        
        row.operator('hg3d.removeipack', icon = 'TRASH')
        
        selected_packs = (True if len(context.scene.installpacks_col) != 0
                          else False)
        row = box.row()
        row.scale_y = 1.5
        row.operator('hg3d.cpackselect',
                     text = 'Select Content Packs',
                     depress = False if selected_packs else True,
                     icon = 'PACKAGE'
                     )
        
        box.label(
            text = 'Select multiple content packs by pressing Ctrl (Windows) or Cmd (Mac)',
            icon = 'INFO'
            )
        box.label(
            text = 'Selected files with a red warning cannot be installed and will be skipped',
            icon = 'INFO'
            )

        if selected_packs:
            #install button section
            box = layout.box()
            box.scale_y = 1.5
            box.label(text = 'STEP 4: Install all your content packs')
            box.operator('hg3d.cpackinstall',
                        text = 'Install All Content Packs',
                        depress =True,
                        icon = 'PACKAGE')
            box.label(
                text = 'Installation time depends on your hardware and the selected packs',
                icon = 'INFO')
    

    def _draw_cpack_editing_ui(self, layout, context):
        split = layout.row(align = True).split(factor=0.3, align = True)
        sidebar = split.box().column()
        col = split.column()
        self._draw_sidebar(sidebar)
        
        box = col.box()
        row = box.row(align = True)
        row.scale_y = 2
        row.prop(self, 'custom_content_categ', expand = True)
        subrow = box.row()
        subrow.prop(self, "hide_other_packs", text = 'Hide content from other packs')
        self._draw_content_grid(col, context)

    def _draw_sidebar(self, sidebar):
        titlebar = sidebar.box().row()
        titlebar.alignment = 'CENTER'
        titlebar.scale_y = 2
        titlebar.label(text = 'Metadata', icon = "ASSET_MANAGER")
        
        sidebar.use_property_split = True
        sidebar.use_property_decorate = False
        sidebar.scale_y = 1.5
        
        sidebar.prop(self, "cpack_name", text = 'Pack name')
        sidebar.prop(self, "cpack_creator", text = 'Creator')
          
        sidebar.prop(self, "cpack_weblink",text = 'Weblink')        
        row = sidebar.row()
        row.prop(self, "cpack_version", text = 'Version')
        row.prop(self, "cpack_subversion", text = '')
        
        sidebar.separator()
        
        a_sidebar = sidebar.column()
        a_sidebar.alert = True
        a_sidebar.operator(
            'hg3d.exit_cpack_edit',
            text='Exit without saving',
            depress=True
        )
        sidebar.operator(
            'hg3d.save_cpack',
            text='Save and export',
            depress=True
        ).export = True

    def _draw_content_grid(self, col, context):
        flow = col.grid_flow()
        pref = get_prefs()
        
        categ = self.custom_content_categ
        for item in filter(lambda i: i.categ == categ, context.scene.custom_content_col):
            if pref.hide_other_packs and item.existing_content:
                continue
            box = flow.box()
            box.label(text = item.name)
            hg_icons = preview_collections['hg_icons']
            gender = item.gender
            if gender != 'none':
                box.label(text = gender.capitalize(), icon_value = hg_icons[f'{gender}_true'].icon_id)
            try:
                box.template_icon(item.icon_value, scale = 5)
            except:
                pass
            incl_icon = "CHECKBOX_HLT" if item.include else "CHECKBOX_DEHLT"
            box.prop(item, 'include', text = 'Include', icon = incl_icon, toggle = True)

#TODO build in preventive system for filepaths instead of dirpaths
class HG_PATHCHANGE(bpy.types.Operator, ImportHelper):
    '''
    Changes the path via file browser popup
    
    Operator Type:
        -Preferences
        -Prop setter
        -Path selection
        
    Prereq:
        None
    '''
    bl_idname      = "hg3d.pathchange"
    bl_label       = "Change Path"
    bl_description = "Change the install path"

    def execute(self,context):
        pref = get_prefs()

        pref.filepath  = self.filepath
        pref.pref_tabs = 'cpacks'
        pref.pref_tabs = 'settings'

        bpy.ops.wm.save_userpref()
        return {'FINISHED'}

class HG_ICON_LEGEND(bpy.types.Panel):
    '''
    Legend popover for the icons used in the ui_list
    '''
    bl_label       = 'Icon legend'
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x  = 8

    def draw (self,context): 
        layout = self.layout       
        hg_icons = preview_collections["hg_icons"]

        icon_dict = {
            'Human Meshes'  : 'humans',
            'Human Textures': 'textures',
            'Shapekeys'     : 'body',
            'Hairstyles'    : 'hair',
            'Poses'         : 'pose',
            'Outfits'       : 'clothing',
            'Footwear'      : 'footwear',
            'Expressions'   : 'expression'
            }

        for icon_desc, icon in icon_dict.items():
            layout.label(text = icon_desc,
                         icon_value = hg_icons[icon].icon_id
                         )
