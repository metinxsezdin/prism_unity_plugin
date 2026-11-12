"""Prism-side windows for the interactive (menu) commands. Never used for interactive=False calls."""

import logging

from .protocol import BridgeError

logger = logging.getLogger(__name__)

# Keep open, non-modal windows alive (Qt deletes unreferenced top-level widgets).
_open_windows = []

UPDATE_ANYWAY = "Update anyway"
CANCEL = "Cancel"


def describe_changes(details):
    lines = []
    for key, label in (("removedNodes", "Removed or renamed objects"), ("removedMaterials", "Removed or renamed materials"),
                       ("addedNodes", "New objects"), ("addedMaterials", "New materials")):
        values = details.get(key) or []
        if values:
            lines.append("%s: %s" % (label, ", ".join(values)))
    return "\n".join(lines)


def import_args(cmds, entity, product, version, record_id=None):
    """Arguments for Unity's importProduct/updateProduct, with the version already resolved.

    Unity must not call back into Prism while Prism's main thread waits for it, so Prism
    resolves the file first and sends it along.
    """
    args = {"version": version, "resolved": cmds.resolveVersion(entity, product, version)}
    if record_id:
        args["recordId"] = record_id
    else:
        args.update(entity=entity, product=product)
    return args


def run_import(cmds, cmd, args):
    """Ask Unity to import/update; on a breaking change, show the diff and ask once."""
    try:
        return cmds.unity.call(cmd, args, interactive=True, timeout=600)
    except BridgeError as e:
        if e.code != "needs_confirmation":
            cmds.core.popup(e.message, title="Prism → Unity")
            return None
        text = "%s\n\n%s" % (e.message, describe_changes(e.details))
        answer = cmds.core.popupQuestion(text, title="Prism → Unity", buttons=[UPDATE_ANYWAY, CANCEL])
        if answer != UPDATE_ANYWAY:
            return None
        confirmed = dict(args, confirm=True)
        try:
            return cmds.unity.call(cmd, confirmed, interactive=True, timeout=600)
        except BridgeError as e2:
            cmds.core.popup(e2.message, title="Prism → Unity")
            return None


def ask_scene_target(cmds):
    """Ask which Prism asset and task an unsaved Unity scene belongs to. None when cancelled."""
    from qtpy.QtWidgets import QInputDialog

    entities = cmds.core.entities
    try:
        assets = sorted(entities.getAssetRelPathFromPath(p).replace("\\", "/") for p in entities.getAssetPaths())
    except Exception:
        assets = []
    asset, ok = QInputDialog.getItem(None, "Save Unity scene in Prism",
                                     "Prism asset for this scene (e.g. Scenes/MeditationRoom):", assets, 0, True)
    if not ok or not asset.strip():
        return None
    task, ok = QInputDialog.getText(None, "Save Unity scene in Prism", "Task name:", text="layout")
    if not ok or not task.strip():
        return None
    return {"entity": {"type": "asset", "asset_path": asset.strip().strip("/")}, "task": task.strip()}


def ask_comment():
    from qtpy.QtWidgets import QInputDialog

    comment, ok = QInputDialog.getText(None, "Save Version", "Comment:")
    return comment if ok else None


def run_playblast(cmds, request):
    """Prism-started playblast. Unity must not call back into Prism while Prism waits on it, so:
    ask Unity for the context, resolve the Prism output here, let Unity render, then register it."""
    context = cmds.unity.call("playblastContext", request, interactive=True)
    entity, task = context["entity"], request.get("task") or context["task"]
    extension = ".mp4" if request.get("format") == "mp4" else ".png"
    target = cmds.playblastTarget(entity, task, extension, request.get("comment", ""))
    sent = dict(request, entity=entity, task=task, outputPath=target["path"])
    result = cmds.unity.call("playblast", sent, interactive=True, timeout=600)
    cmds.playblastDone(result["outputPath"], entity, task, request.get("comment", ""),
                       {k: request.get(k) for k in ("mode", "frames", "fps", "width", "height", "format")})
    return dict(result, version=target["version"])


def open_playblast_dialog(cmds):
    from qtpy.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox)

    cameras = cmds.unity.call("listCameras") or []
    dlg = QDialog()
    dlg.setWindowTitle("Unity Playblast")
    form = QFormLayout(dlg)
    mode = QComboBox()
    mode.addItem("Turntable of the selected objects", "turntable")
    mode.addItem("Scene camera", "free")
    camera = QComboBox()
    for cam in cameras:
        camera.addItem(cam["name"], cam["path"])
    width, height, frames, fps = QSpinBox(), QSpinBox(), QSpinBox(), QSpinBox()
    for box, lo, hi, val in ((width, 16, 8192, 1920), (height, 16, 8192, 1080), (frames, 1, 10000, 120), (fps, 1, 240, 30)):
        box.setRange(lo, hi)
        box.setValue(val)
    fmt = QComboBox()
    fmt.addItem("Image sequence (PNG)", "png")
    fmt.addItem("Video (MP4)", "mp4")
    comment = QLineEdit()
    for label, widget in (("Mode", mode), ("Camera", camera), ("Width", width), ("Height", height),
                          ("Frames", frames), ("FPS", fps), ("Format", fmt), ("Comment", comment)):
        form.addRow(label, widget)
    camera.setEnabled(False)
    mode.currentIndexChanged.connect(lambda _: camera.setEnabled(mode.currentData() == "free"))
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    form.addRow(buttons)

    def accept():
        request = {"mode": mode.currentData(), "width": width.value(), "height": height.value(),
                   "frames": frames.value(), "fps": fps.value(), "format": fmt.currentData(), "comment": comment.text()}
        if request["mode"] == "free":
            request["cameraPath"] = camera.currentData()
        dlg.close()
        try:
            result = run_playblast(cmds, request)
        except BridgeError as e:
            cmds.core.popup(e.message, title="Unity Playblast")
            return
        cmds.core.popup("Playblast %s saved:\n%s" % (result["version"], result["outputPath"]), title="Unity Playblast", severity="info")

    buttons.accepted.connect(accept)
    buttons.rejected.connect(dlg.close)
    dlg.finished.connect(lambda _: _open_windows.remove(dlg) if dlg in _open_windows else None)
    _open_windows.append(dlg)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()


def run_mark_missing(cmds, entries, present=()):
    """Tell Unity which packages' products disappeared from Prism (nothing is deleted) and which are back.

    Returns the ids newly flagged missing. Failures (Unity in Play Mode or compiling, no packaging
    package) are logged and never stop the check.
    """
    changed = []
    for ids, missing in (([e["id"] for e in entries if e.get("missing")], True), (list(present), False)):
        if not ids:
            continue
        try:
            answer = cmds.unity.call("setPrismMissing", {"ids": ids, "missing": missing}, interactive=True)
        except BridgeError as e:
            logger.warning("Could not update the prismMissing flags in Unity: %s", e)
            continue
        if missing and isinstance(answer, dict):
            changed = list(answer.get("changed") or [])
    return changed


def entity_from_product_data(data):
    return {k: data[k] for k in ("type", "asset_path", "sequence", "shot") if data.get(k)}


def open_import_browser(cmds):
    import ProductBrowser
    from qtpy.QtCore import QTimer

    browser = ProductBrowser.ProductBrowser(core=cmds.core)
    browser.handleImport = False
    browser.autoClose = True
    browser.setWindowTitle("Import into Unity")

    def on_path(path):
        data = cmds.core.products.getProductDataFromFilepath(path) or {}

        def go():
            try:
                args = import_args(cmds, entity_from_product_data(data), data.get("product"), data.get("version") or "latest")
            except BridgeError as e:
                cmds.core.popup(e.message, title="Prism → Unity")
                return
            run_import(cmds, "importProduct", args)

        QTimer.singleShot(0, go)

    browser.productPathSet.connect(on_path)
    browser.closing.connect(lambda: _open_windows.remove(browser) if browser in _open_windows else None)
    _open_windows.append(browser)
    browser.show()
    browser.raise_()
    browser.activateWindow()


def check_window_title(outdated, missing):
    return "Prism: new versions for Unity" if outdated else "Prism: products removed from Prism"


def open_check_versions(cmds, outdated, missing=()):
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout

    dlg = QDialog()
    dlg.setWindowTitle(check_window_title(outdated, missing))
    layout = QVBoxLayout(dlg)
    if missing:
        names = ", ".join(e["id"] for e in missing)
        note = QLabel("No longer in Prism (kept in Unity, marked as missing): %s" % names)
        note.setWordWrap(True)
        layout.addWidget(note)
    if outdated:
        layout.addWidget(QLabel("These Prism products have newer versions than the ones in this Unity project:"))
    items = QListWidget()
    for entry in outdated:
        item = QListWidgetItem("%s    %s → %s" % (entry["id"], entry["current"], entry["latest"]))
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setData(Qt.UserRole, entry)
        items.addItem(item)
    items.setVisible(bool(outdated))
    layout.addWidget(items)
    buttons = QDialogButtonBox()
    update = buttons.addButton("Update selected", QDialogButtonBox.AcceptRole)
    update.setVisible(bool(outdated))
    buttons.addButton("Close", QDialogButtonBox.RejectRole)
    layout.addWidget(buttons)

    def do_update():
        for i in range(items.count()):
            item = items.item(i)
            if item.checkState() == Qt.Checked:
                entry = item.data(Qt.UserRole)
                try:
                    args = import_args(cmds, entry["entity"], entry["product"], entry["latest"], record_id=entry["id"])
                except BridgeError as e:
                    cmds.core.popup(e.message, title="Prism → Unity")
                    continue
                run_import(cmds, "updateProduct", args)
        dlg.close()

    update.clicked.connect(do_update)
    buttons.rejected.connect(dlg.close)
    dlg.finished.connect(lambda _: _open_windows.remove(dlg) if dlg in _open_windows else None)
    _open_windows.append(dlg)
    dlg.resize(560, 320)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
