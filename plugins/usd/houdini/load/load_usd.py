import os

import avalon.api
from reveries.plugins import PackageLoader


class HoudiniUSDLoader(PackageLoader, avalon.api.Loader):
    """Load the model"""

    label = "Load USD"
    order = -10
    icon = "download"
    color = "orange"

    hosts = ["houdini"]

    families = [
        "reveries.model",
        "reveries.pointcache",
        "reveries.look.asset_prim",
        "reveries.ani.ani_prim"
    ]

    representations = [
        "USD",
    ]

    def load(self, context, name, namespace, data):
        import hou

        # Check publish folder exists
        directory = self.package_path
        if not os.path.exists(str(directory)):
            hou.ui.displayMessage("Publish folder not exists:\n{}".format(directory),
                                  severity=hou.severityType.Warning)
            return

        # Check usd file already published
        files = os.listdir(directory)
        if not files:
            hou.ui.displayMessage("Can't found usd file in publish folder:\n{}".format(directory),
                                  severity=hou.severityType.Warning)
            return

        usd_file = os.path.join(directory, files[0])
        asset_name = context['asset']['name']
        subset_data = context['subset']

        usd_info = {
            'asset_name': asset_name,
            'subset_name': subset_data['name'],
            'family_name': subset_data['data']['families'],
            'file_path': usd_file
        }

        self._add_usd(usd_info)

    def _add_usd(self, usd_info):
        """
        Add reference/sublayer in subnet node.
        :param usd_info: dict.
        usd_info = {
            'asset_name': 'BoxB',
            'subset_name': 'assetPrim',
            'family_name': 'reveries.look.asset_prim',
            'file_path': "Q:/199909_AvalonPlay/Avalon/PropBox/BoxB/publish/assetPrim/v002/USD/asset_prim.usda"
        }
        :return:
        """
        import hou
        from reveries.houdini.usd.add_usd_file import update_node

        stage = hou.node("/stage/")

        # Check selective node
        node = hou.selectedNodes()
        if not node:
            node = stage.createNode("subnet_usd", 'subnet_usd')
        else:
            node = node[0]

        update_node(node, usd_info)
        print 'Current node: {}'.format(node)
        print 'Add done.\nInfo: {}\n'.format(usd_info)