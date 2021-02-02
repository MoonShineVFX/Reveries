
import pyblish.api
from reveries import plugins


class SelectUnknownNodes(plugins.MayaSelectInvalidContextAction):

    label = "Select Unknown"


class DeleteUnknownNodes(plugins.RepairContextAction):

    label = "Delete Unknown"


class ValidateNoUnknownNodes(pyblish.api.InstancePlugin):
    """Can not publish unknown nodes
    """

    order = pyblish.api.ValidatorOrder - 0.1
    label = "No Unknown Nodes"
    host = ["maya"]
    families = [
        "reveries.model",
        "reveries.rig",
        "reveries.look",
        "reveries.xgen",
        "reveries.camera",
        "reveries.mayashare",
        "reveries.standin",
        "reveries.rsproxy",
        "reveries.lightset",
    ]

    actions = [
        pyblish.api.Category("Select"),
        SelectUnknownNodes,
        pyblish.api.Category("Fix It"),
        DeleteUnknownNodes,
    ]

    @classmethod
    def get_invalid(cls, context):
        from maya import cmds
        return [node for node in cmds.ls(type="unknown")
                if not cmds.referenceQuery(node, isNodeReferenced=True)]

    @plugins.context_process
    def process(self, context):
        unknown = self.get_invalid(context)

        for node in unknown:
            self.log.error(node)

        if unknown:
            raise Exception("Scene contain unknown nodes.")

    @classmethod
    def fix_invalid(cls, context):
        """Delete unknown nodes"""
        from maya import cmds
        unknown_nodes = cls.get_invalid(context)
        lock_state = cmds.lockNode(unknown_nodes, query=True)
        for item, locked in zip(unknown_nodes, lock_state):
            if not cmds.objExists(item):
                continue
            if locked:
                cmds.lockNode(item, lock=False)
            cmds.delete(item)
