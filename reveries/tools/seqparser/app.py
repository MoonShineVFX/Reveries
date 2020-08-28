
import sys
import os
from avalon.vendor.Qt import QtWidgets, QtCore
from avalon.vendor import qtawesome
from avalon.tools import lib as tools_lib
from avalon import style

from ...lib import pindict
from ... import plugins
from .. import widgets as tool_widgets
from . import widgets, command


module = sys.modules[__name__]
module.window = None


class Window(QtWidgets.QDialog):

    def __init__(self, root=None, callback=None, with_keys=None, parent=None):
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
                "options": QtWidgets.QWidget(),
                "single": QtWidgets.QCheckBox("Include Single Frame"),
                "stereo": QtWidgets.QCheckBox("Pair Stereo Sequences"),
                "nameRegex": QtWidgets.QWidget(),
                "label": QtWidgets.QLabel("Channel Name: "),
                "nHead": QtWidgets.QLineEdit(),
                "nTail": QtWidgets.QLineEdit(),
                "view": widgets.SequenceWidget(),
            },

            "endDialog": {
                "main": QtWidgets.QWidget(),
                "accept": QtWidgets.QPushButton("Accept"),
                "cancel": QtWidgets.QPushButton("Cancel"),
                "callback": callback,
                "with_keys": with_keys,
            },
        })

        with data.pin("rootPath") as root_path:
            layout = QtWidgets.QHBoxLayout(root_path["main"])
            layout.addWidget(root_path["label"])
            layout.addWidget(root_path["path"], stretch=True)
            layout.addWidget(root_path["find"])
            layout.setContentsMargins(4, 0, 4, 0)

        with data.pin("sequences") as sequences:
            layout = QtWidgets.QHBoxLayout(sequences["options"])
            layout.addWidget(sequences["single"])
            layout.addSpacing(5)
            layout.addWidget(sequences["stereo"])
            layout.addStretch()
            layout.setContentsMargins(2, 2, 2, 2)
            layout = QtWidgets.QHBoxLayout(sequences["nameRegex"])
            layout.addWidget(sequences["label"])
            layout.addWidget(sequences["nHead"], stretch=True)
            layout.addWidget(sequences["nTail"], stretch=True)
            layout.setContentsMargins(2, 2, 2, 2)
            layout = QtWidgets.QVBoxLayout(sequences["main"])
            layout.addWidget(sequences["options"])
            layout.addSpacing(8)
            layout.addWidget(sequences["nameRegex"])
            layout.addWidget(sequences["view"])
            layout.setContentsMargins(4, 6, 4, 0)

        with data.pin("endDialog") as end_dialog:
            layout = QtWidgets.QHBoxLayout(end_dialog["main"])
            layout.addWidget(end_dialog["accept"])
            layout.addWidget(end_dialog["cancel"])
            layout.setContentsMargins(4, 0, 4, 0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(data["rootPath"]["main"])
        layout.addWidget(data["sequences"]["main"], stretch=True)
        layout.addWidget(data["endDialog"]["main"])

        if root:
            data["rootPath"]["path"].setText(root)
            data["rootPath"]["find"].setEnabled(False)
            data["sequences"]["single"].setEnabled(False)
        data["rootPath"]["path"].setReadOnly(True)

        data["rootPath"]["path"].textChanged.connect(self.find_sequences)
        data["rootPath"]["find"].clicked.connect(self.open_browser)

        data["sequences"]["single"].stateChanged.connect(self.on_single)
        data["sequences"]["stereo"].stateChanged.connect(self.on_stereo)

        data["sequences"]["nHead"].textChanged.connect(self.on_nhead_changed)
        data["sequences"]["nTail"].textChanged.connect(self.on_ntail_changed)

        data["endDialog"]["accept"].clicked.connect(self.on_accepted)
        data["endDialog"]["cancel"].clicked.connect(self.reject)

        self.data = data

        # Defaults
        self.is_single = False
        self.is_stereo = False
        self.from_cache = False
        self.resize(600, 800)

    def collected(self, with_keys=None):
        return self.data["sequences"]["view"].collected(with_keys)

    def get_root_path(self):
        return self.data["rootPath"]["path"].text()

    def on_single(self, state):
        self.is_single = bool(state)
        # Skip if from cache
        if not self.from_cache:
            self.find_sequences(self.get_root_path())

    def on_stereo(self, state):
        self.is_stereo = bool(state)
        self.data["sequences"]["view"].set_stereo(bool(state))

    def on_accepted(self):
        with_keys = self.data["endDialog"]["with_keys"]
        collected = self.collected(with_keys)
        # Skip save if loaded from cache
        if not self.from_cache:
            command.save_cache(collected,
                               output_dir=self.get_root_path(),
                               is_stereo=self.is_stereo,
                               is_single=self.is_single,
                               created_by="seqparser",
                               padding_string=None,
                               start=None,
                               end=None)
        self.run_callback(collected)

        self.accept()

    def run_callback(self, collected):
        callback = self.data["endDialog"]["callback"]
        if callback is not None:
            callback(collected)

    def open_browser(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(parent=self)
        if path:
            self.data["rootPath"]["path"].setText(path)

    def find_sequences(self, path):
        if path and not os.path.isdir(path):
            message = "Not a valid folder: %s" % path
            plugins.message_box_error(title="Error",
                                      message=message)
            print(message)
            return

        data = command.load_cache(path)
        if data is None:
            self.from_cache = False
            self.ls_sequences(path)
            return

        self.from_cache = True

        # Process cache data
        cache = data["cache"]
        cache_start = data["start"]
        cache_end = data["end"]
        cache_padding = data["paddingStr"]
        is_stereo = data["isStereo"]
        is_single = data["isSingle"]
        created_by = data["createdBy"]

        print("Loading sequences from '%s' created cache.." % created_by)
        sequences = list()

        for name, item in cache.items():
            item["name"] = name

            if cache_padding is not None:
                item["paddingStr"] = cache_padding
            if cache_start is not None:
                item["start"] = cache_start
            if cache_end is not None:
                item["end"] = cache_end

            sequences.append(item)

        self.add_sequences(sequences)

        # Update widget
        if is_stereo:
            state = QtCore.Qt.Checked if is_stereo else QtCore.Qt.Unchecked
            self.data["sequences"]["stereo"].setCheckState(state)
        if is_single:
            state = QtCore.Qt.Checked if is_single else QtCore.Qt.Unchecked
            self.data["sequences"]["single"].setCheckState(state)

    def ls_sequences(self, path):
        min_length = 1 if self.is_single else 2

        sequences = list()
        max_sequence = 50
        # Pop up a progress dialog for interruption
        with tool_widgets.Interrupter(
                title="Scanning sequences",
                label=("Progress unknown, this may take a while.\n"
                       "Press 'Cancel' to stop."),
                minimum=0,
                maximum=10,  # Don't know where is the end
        ) as progress:
            # (TODO) Run in worker thread

            for i, item in enumerate(command.ls_sequences(path,
                                                          min_length)):
                if progress.is_canceled():
                    return

                if i > max_sequence:
                    # Prompt dialog asking continue the process or not
                    respond = plugins.message_box_warning(
                        title="Warning",
                        message=("Found over %d sequences, do you wish to "
                                 "continue ?" % max_sequence),
                        optional=True
                    )
                    if respond:
                        # Double it
                        max_sequence += max_sequence
                    else:
                        return

                sequences.append(item)
                progress.bump()  # Also keep dialog responsive

        self.add_sequences(sequences)

    def add_sequences(self, sequences):
        self.data["sequences"]["view"].add_sequences(sequences)

    def on_nhead_changed(self, head):
        tail = self.data["sequences"]["nTail"].text()
        self.data["sequences"]["view"].search_channel_name(head, tail)

    def on_ntail_changed(self, tail):
        head = self.data["sequences"]["nHead"].text()
        self.data["sequences"]["view"].search_channel_name(head, tail)


def show(callback=None, with_keys=None, parent=None):
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
            return
        except RuntimeError as e:
            if not str(e).rstrip().endswith("already deleted."):
                raise

            # Garbage collected
            module.window = None

    with tools_lib.application():
        window = Window(callback=callback, with_keys=with_keys, parent=parent)
        window.show()
        window.setStyleSheet(style.load_stylesheet())

        module.window = window


def show_on_stray(root, sequences, framerange, parent=None):
    """Used for renderlayer loader to pick up nu-documented sequences

    DEPRECATED

    """
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
