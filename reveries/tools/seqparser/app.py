
import sys
import os
from avalon.vendor.Qt import QtWidgets, QtCore
from avalon.vendor import qtawesome
from avalon.tools import lib as tools_lib
from avalon import style

from ...lib import pindict
from . import widgets, command


module = sys.modules[__name__]
module.window = None


class Window(QtWidgets.QDialog):

    def __init__(self, root=None, callback=None, parent=None):
        super(Window, self).__init__(parent=parent)
        self.setWindowTitle("Setup Sequences")

        icon_dir = qtawesome.icon("fa.folder-open", color="gray")

        data = pindict.to_pindict({
            "rootPath": {
                "main": QtWidgets.QWidget(),
                "label": QtWidgets.QLabel("Root: "),
                "path": QtWidgets.QLineEdit(),
                "find": QtWidgets.QPushButton(icon_dir, "Browse.."),
            },

            "sequences": {
                "main": QtWidgets.QWidget(),
                "view": widgets.SequenceWidget(),
            },

            "endDialog": {
                "main": QtWidgets.QWidget(),
                "accept": QtWidgets.QPushButton("Accept"),
                "cancel": QtWidgets.QPushButton("Cancel"),
                "callback": callback,
            },
        })

        with data.pin("rootPath") as root_path:
            layout = QtWidgets.QHBoxLayout(root_path["main"])
            layout.addWidget(root_path["label"])
            layout.addWidget(root_path["path"], stretch=True)
            layout.addWidget(root_path["find"])

        with data.pin("sequences") as sequences:
            layout = QtWidgets.QHBoxLayout(sequences["main"])
            layout.addWidget(sequences["view"])

        with data.pin("endDialog") as end_dialog:
            layout = QtWidgets.QHBoxLayout(end_dialog["main"])
            layout.addWidget(end_dialog["accept"])
            layout.addWidget(end_dialog["cancel"])

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(data["rootPath"]["main"])
        layout.addWidget(data["sequences"]["main"], stretch=True)
        layout.addWidget(data["endDialog"]["main"])

        if root:
            data["rootPath"]["path"].setText(root)
            data["rootPath"]["find"].setEnabled(False)
        data["rootPath"]["path"].setReadOnly(True)

        data["rootPath"]["path"].textChanged.connect(self.ls_sequences)
        data["rootPath"]["find"].clicked.connect(self.open_browser)

        data["endDialog"]["accept"].clicked.connect(self.run_callback)
        data["endDialog"]["accept"].clicked.connect(self.accept)
        data["endDialog"]["cancel"].clicked.connect(self.reject)

        self.data = data

        # Defaults
        self.resize(600, 800)

    def collected(self, with_keys=None):
        return self.data["sequences"]["view"].collected(with_keys)

    def run_callback(self):
        callback = self.datadata["endDialog"]["callback"]
        if callback is not None:
            callback(self.collected())

    def open_browser(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(parent=self)
        if path:
            self.data["rootPath"]["path"].setText(path)

    def ls_sequences(self, path):
        if not os.path.isdir(path):
            print("Not a valid path.")
            return

        sequences = list()
        max_sequence = 50
        for i, item in enumerate(command.ls_sequences(path)):
            if i > max_sequence:
                # (TODO) Prompt dialog asking continue the process or not
                print("Too many sequences.")
                return

            sequences.append(item)

        self.add_sequences(sequences)

    def add_sequences(self, sequences):
        self.data["sequences"]["view"].add_sequences(sequences)


def show(callback=None, parent=None):
    """Display Main GUI"""
    # Remember window
    if module.window is not None:
        try:
            module.window.show()

            # If the window is minimized then unminimize it.
            if module.window.windowState() & QtCore.Qt.WindowMinimized:
                module.window.setWindowState(QtCore.Qt.WindowActive)

            # Raise and activate the window
            module.window.raise_()             # for MacOS
            module.window.activateWindow()     # for Windows
            module.window.refresh()
            return
        except RuntimeError as e:
            if not str(e).rstrip().endswith("already deleted."):
                raise

            # Garbage collected
            module.window = None

    with tools_lib.application():
        window = Window(callback=callback, parent=parent)
        window.show()
        window.setStyleSheet(style.load_stylesheet())

        module.window = window


def show_on_stray(root, sequences, framerange, parent=None):
    start, end = framerange
    min_length = 1 if start == end else 2

    # Resolve path
    _resolved = dict()
    for aov_name, data in sequences.items():
        if "fname" in data:
            tail = "%s/%s" % (aov_name, data["fname"])
        else:
            tail = data["fpattern"]

        padding = tail.count("#")
        if padding:
            frame_str = "%%0%dd" % padding
            tail = tail.replace("#" * padding, frame_str)
        data["fpattern"] = tail.replace("\\", "/")

        path = os.path.join(root, tail).replace("\\", "/")
        data["_resolved"] = path
        data["name"] = aov_name
        _resolved[path] = data

    # Find stray sequence
    stray = list()
    for item in command.ls_sequences(root, min_length):
        part = (item["root"], "/", item["fpattern"])
        if "".join(part) not in _resolved:
            stray.append(item)

    if stray:

        resolved = list()
        for path, data in _resolved.items():
            fpattern = os.path.relpath(path, root).replace("\\", "/")
            files = [fpattern % i for i in range(int(start), int(end) + 1)]
            item = command.assemble(root, files, min_length)
            item.update(data)
            resolved.append(item)

        with tools_lib.application():
            window = Window(root=root, parent=parent)
            # window.setModal(True)
            window.setStyleSheet(style.load_stylesheet())

            window.add_sequences(stray + resolved)

            if window.exec_():
                sequences = window.collected(with_keys=["name", "resolution"])

    # (TODO) Remember resolved ?

    return sequences
