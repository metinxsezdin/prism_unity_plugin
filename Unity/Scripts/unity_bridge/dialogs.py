"""Prism-side windows for the interactive (menu) commands. Never used for interactive=False calls."""

from .protocol import BridgeError

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


def open_check_versions(cmds, outdated):
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout

    dlg = QDialog()
    dlg.setWindowTitle("Prism: new versions for Unity")
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("These Prism products have newer versions than the ones in this Unity project:"))
    items = QListWidget()
    for entry in outdated:
        item = QListWidgetItem("%s    %s → %s" % (entry["id"], entry["current"], entry["latest"]))
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setData(Qt.UserRole, entry)
        items.addItem(item)
    layout.addWidget(items)
    buttons = QDialogButtonBox()
    update = buttons.addButton("Update selected", QDialogButtonBox.AcceptRole)
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
