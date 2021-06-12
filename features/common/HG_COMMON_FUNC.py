import os
import bpy #type: ignore

"""
Contains functions that get used a lot by other operators
"""  

def add_to_collection(context, obj, collection_name = 'HumGen'):
    """
    Adds the given object to the given collection
    """  
    try: 
        collection = bpy.data.collections[collection_name]
    except:
        collection = bpy.data.collections.new(name= collection_name )
        if collection_name == "HumGen_Backup [Don't Delete]":
            bpy.data.collections["HumGen"].children.link(collection)
            context.view_layer.layer_collection.children['HumGen'].children[collection_name].exclude = True
        else:
            context.scene.collection.children.link(collection)

    try:
        context.scene.collection.objects.unlink(obj)
    except:
        obj.users_collection[0].objects.unlink(obj)

    collection.objects.link(obj)

    return collection


def get_prefs():
    addon_name = __package__.split('.')[0]
    return bpy.context.preferences.addons[addon_name].preferences

def find_human(obj):
    """
    Used extensively to find the hg_rig object corresponding to the selected object. 
    This makes sure the add-on works as expected, even if a child object of the rig is selected. 
    Returns none if object is not part of a human, otherwise returns hg_rig
    """  
    if not obj:
        return None
    elif not obj.HG.ishuman:
        if obj.parent:
            if obj.parent.HG.ishuman:
                return obj.parent
        else:
            return None
    else:
        return obj


def apply_shapekeys(ob):
    """
    Applies all shapekeys on the given object, so modifiers on the object can be applied
    """  
    bpy.context.view_layer.objects.active = ob
    if not ob.data.shape_keys:
        return

    bpy.ops.object.shape_key_add(from_mix=True)
    ob.active_shape_key.value = 1.0
    ob.active_shape_key.name  = "All shape"
    
    i = ob.active_shape_key_index

    for n in range(1,i):
        ob.active_shape_key_index = 1
        ob.shape_key_remove(ob.active_shape_key)
            
    ob.shape_key_remove(ob.active_shape_key)   
    ob.shape_key_remove(ob.active_shape_key)
            

def ShowMessageBox(message = "", title = "Human Generator - Alert", icon = 'INFO'):
    """
    shows a warning popup with the given text
    """
    def draw(self, context):
        self.layout.label(text = message)

    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def ShowConfirmationBox(message = '', title = "Human Generator - Alert", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(text = message)

    bpy.context.window_manager.invoke_props_dialog(draw)

def make_path_absolute(key):
    """ Prevent Blender's relative paths of doom """
    # This can be a collection property or addon preferences
    props = bpy.context.scene.HG3D 
    sane_path = lambda p: os.path.abspath(bpy.path.abspath(p)) 
    if key in props and props[key].startswith('//'):
        props[key] = sane_path(props[key])


#TODO make deepclean data removal, using:

#bpy.data.objects.remove(obj)

# for block in bpy.data.meshes:
#     if block.users == 0:
#         bpy.data.meshes.remove(block)

# for block in bpy.data.materials:
#     if block.users == 0:
#         bpy.data.materials.remove(block)

# for block in bpy.data.textures:
#     if block.users == 0:
#         bpy.data.textures.remove(block)

# for block in bpy.data.images:
#     if block.users == 0:
#         bpy.data.images.remove(block)

#TODO add pre-save handler