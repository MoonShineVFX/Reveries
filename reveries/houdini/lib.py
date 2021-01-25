import uuid

from contextlib import contextmanager

import hou
import os
import json

from avalon import api, io
from avalon.houdini import lib as houdini


# Get Houdini root node
sceneRoot = hou.node('/obj/')


def set_id(node, unique_id, overwrite=False):

    exists = node.parm("id")
    if not exists:
        houdini.imprint(node, {"id": unique_id})

    if not exists and overwrite:
        node.setParm("id", unique_id)


def get_id(node):
    """
    Get the `cbId` attribute of the given node
    Args:
        node (hou.Node): the name of the node to retrieve the attribute from

    Returns:
        str

    """

    if node is None:
        return

    id = node.parm("id")
    if node is None:
        return
    return id


def generate_ids(nodes, asset_id=None):
    """Returns new unique ids for the given nodes.

    Note: This does not assign the new ids, it only generates the values.

    To assign new ids using this method:
    >>> nodes = ["a", "b", "c"]
    >>> for node, id in generate_ids(nodes):
    >>>     set_id(node, id)

    To also override any existing values (and assign regenerated ids):
    >>> nodes = ["a", "b", "c"]
    >>> for node, id in generate_ids(nodes):
    >>>     set_id(node, id, overwrite=True)

    Args:
        nodes (list): List of nodes.
        asset_id (str or bson.ObjectId): The database id for the *asset* to
            generate for. When None provided the current asset in the
            active session is used.

    Returns:
        list: A list of (node, id) tuples.

    """

    if asset_id is None:
        # Get the asset ID from the database for the asset of current context
        asset_data = io.find_one({"type": "asset",
                                  "name": api.Session["AVALON_ASSET"]},
                                 projection={"_id": True})
        assert asset_data, "No current asset found in Session"
        asset_id = asset_data['_id']

    node_ids = []
    for node in nodes:
        _, uid = str(uuid.uuid4()).rsplit("-", 1)
        unique_id = "{}:{}".format(asset_id, uid)
        node_ids.append((node, unique_id))

    return node_ids


def get_id_required_nodes():

    valid_types = ["geometry"]
    nodes = {n for n in hou.node("/out").children() if
             n.type().name() in valid_types}

    return list(nodes)


def get_additional_data(container):
    """Not implemented yet!"""
    return container


def set_parameter_callback(node, parameter, language, callback):
    """Link a callback to a parameter of a node

    Args:
        node(hou.Node): instance of the nodee
        parameter(str): name of the parameter
        language(str): name of the language, e.g.: python
        callback(str): command which needs to be triggered

    Returns:
        None

    """

    template_grp = node.parmTemplateGroup()
    template = template_grp.find(parameter)
    if not template:
        return

    script_language = (hou.scriptLanguage.Python if language == "python" else
                       hou.scriptLanguage.Hscript)

    template.setScriptCallbackLanguage(script_language)
    template.setScriptCallback(callback)

    template.setTags({"script_callback": callback,
                      "script_callback_language": language.lower()})

    # Replace the existing template with the adjusted one
    template_grp.replace(parameter, template)

    node.setParmTemplateGroup(template_grp)


def set_parameter_callbacks(node, parameter_callbacks):
    """Set callbacks for multiple parameters of a node

    Args:
        node(hou.Node): instance of a hou.Node
        parameter_callbacks(dict): collection of parameter and callback data
            example:  {"active" :
                        {"language": "python",
                         "callback": "print('hello world)'"}
                     }
    Returns:
        None
    """
    for parameter, data in parameter_callbacks.items():
        language = data["language"]
        callback = data["callback"]

        set_parameter_callback(node, parameter, language, callback)


def get_output_parameter(node):
    """Return the render output parameter name of the given node

    Example:
        root = hou.node("/obj")
        my_alembic_node = root.createNode("alembic")
        get_output_parameter(my_alembic_node)
        # Result: "output"

    Args:
        node(hou.Node): node instance

    Returns:
        hou.Parm

    """

    node_type = node.type().name()
    if node_type == "geometry":
        return node.parm("sopoutput")

    elif node_type == "alembic":
        return node.parm("filename")

    elif node_type == "arnold":
        if node.parm("ar_ass_export_enable").eval():
            return node.parm("ar_ass_file")
        else:
            return node.parm("ar_picture")
    elif node_type == "usd":
        return node.parm("lopoutput")
    else:
        raise TypeError("Node type '%s' not supported" % node_type)


@contextmanager
def attribute_values(node, data):

    previous_attrs = {key: node.parm(key).eval() for key in data.keys()}
    try:
        node.setParms(data)
        yield
    except Exception:
        pass
    finally:
        node.setParms(previous_attrs)


def set_scene_fps(fps):
    hou.setFps(fps)


def export_nodes(nodes_paths, file_path):
    """Export nodes as text file.

    Example:
        sceneRoot = hou.node('/obj/')
        nodes_paths = ["/obj/nono_shader_day", "/obj/nono_shader_night"]
        file = "O:/Project/Char/Nono/publish/Nono_shader.cpio"
        export_nodes(nodes_paths, file)
        # Result: "output file"

    Args:
        nodes_paths(list): List of nodes' path
        file_path(str): cpio format file path

    """

    nodes = hou.nodes(nodes_paths)
    path = os.path.abspath(file_path)
    sceneRoot.saveChildrenToFile(nodes, [], path)


def load_nodes(file_path):
    """Load nodes from text file.

    Example:
        sceneRoot = hou.node('/obj/')
        file = "O:/Project/Char/Nono/publish/Nono_shader.cpio"
        load_nodes(file)

    Args:
        file_path(str): cpio format file path

    Returns:
        hou.Nodes

    """

    file = os.path.abspath(file_path)
    sceneRoot.loadItemsFromFile(file)


def export_shaderparm(node, shader_file_path):
    """Export char nodes's shader parm to file.

    Example:
        char = hou.node("/obj/char_nono")
        char_shader_path = "O:/Project/Char/Nono/publish/stylesheet.json"
        export_shaderparm(char, char_shader_path)
        # Result: "output file"

    Args:
        node(hou.Node): node instance
        shader_file_path(str): json format file path

    """
    stylesheet_data = node.parm('shop_materialstylesheet').eval()
    with open(shader_file_path, 'w') as f:
        f.write(stylesheet_data)
        f.close()


def assign_shaderparm(node, shader_file_path):
    """Add shader parm to node by reading shader file's data.

    Example:
        char = hou.node("/obj/char_nono")
        char_shader_path = "O:/Project/Char/Nono/publish/stylesheet.json"
        assign_shaderparm(char, char_shader_path)
        # Result: "output"

    Args:
        node(hou.Node): node instance
        shader_file_path(str): json format file path

    Returns:
        hou.Parm

    """

    data_tags = {
        'script_action_icon': 'DATATYPES_stylesheet',
        'script_action_help': 'Open in Material Style Sheet editor.',
        'spare_category': 'Shaders',
        'script_action': """
import tooltils
p = toolutils.dataTree('Material Style Sheets')
p.setCurrentPath(kwargs['node'].path() + '/Style Sheet Parameter')
        """,
        'editor': '1'
    }
    group = node.parmTemplateGroup()
    folder = hou.FolderParmTemplate('folder', 'Shaders')
    parm_string = hou.StringParmTemplate(
        name='shop_materialstylesheet',
        label='Material Style Sheet',
        num_components=1,
        tags=data_tags
    )
    folder.addParmTemplate(parm_string)
    group.append(folder)
    node.setParmTemplateGroup(group)

    with open(shader_file_path, 'r') as file:
        data = json.load(file)
        data_convert = json.dumps(data, indent=4)
        node.parm('shop_materialstylesheet').set(data_convert)
        file.close()


def create_empty_shadernetwork(asset_name):
    """Create asset's SOP shader network.

    Example:
        sceneRoot = hou.node('/obj/')
        name = "char_nono"
        create_empty_shadernetwork(name)

    Args:
        asset_name(str): name of the asset

    Returns:
        hou.Nodes

    """
    NODE_COLOR = (0.282353, 0.819608, 0.8)
    NODE_POS = (3, 0)

    shaderpack_name = 'SHADER_' + asset_name.upper()
    shaderpack_node = sceneRoot.createNode('geo', shaderpack_name)
    shaderpack_node.setColor(hou.Color(*NODE_COLOR))

    shaderpack_node.createNode('shopnet', 'shopnet')
    shaderpack_node.createNode('matnet', 'matnet').setPosition(
        hou.Vector2(*NODE_POS)
    )
    shaderpack_node.setCurrent(on=True, clear_all_selected=True)
    shaderpack_node.setDisplayFlag(True)
