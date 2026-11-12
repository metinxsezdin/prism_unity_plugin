"""One Prism core per server process, loaded on first use, never showing a window."""

import os

from unity_bridge.headless import headless
from unity_bridge.protocol import BridgeError

from . import audit

TEAM_PRISM_VERSION = "v2.1.2.1"


def create_core():
    """Load PrismCore without UI. Prism needs a Qt application; it is created offscreen."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import PrismCore
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    core = PrismCore.create(app="Standalone", prismArgs=["noUI", "silent"])
    core._prismMcpQtApp = app  # keep the application alive as long as the core
    return core


class Session(object):
    def __init__(self, core_factory=None, audit_path=None):
        self._factory = core_factory or create_core
        self._core = None
        self.audit_path = audit_path or audit.DEFAULT_PATH

    @property
    def core(self):
        if self._core is None:
            try:
                core = self._factory()
            except BridgeError:
                raise
            except BaseException as e:  # SystemExit from Prism included
                raise BridgeError("prism_unavailable", "Prism could not start: %s: %s" % (type(e).__name__, e))
            if core is None:
                raise BridgeError("prism_unavailable", "Prism could not start.")
            self._core = core
        return self._core

    def run(self, fn):
        """fn(core) with every Prism dialog turned into an error."""
        core = self.core
        with headless(core):
            return fn(core)

    def project_info(self):
        core = self._core
        if core is None or not getattr(core, "prismIni", ""):
            return None
        return {"name": getattr(core, "projectName", ""), "path": (getattr(core, "projectPath", "") or "").replace("\\", "/")}

    def require_project(self):
        core = self.core
        if not getattr(core, "prismIni", ""):
            raise BridgeError("needs_input", "No Prism project is active. Pick one with set_project.", {"missing": ["prismProject"]})
        if not os.path.isdir(core.projectPath or ""):
            raise BridgeError("source_unavailable", "The project folder is not reachable: %s (is the drive connected?)" % core.projectPath,
                              {"path": core.projectPath})
        return core

    def user(self):
        try:
            return self._core.users.getUser() if self._core is not None else None
        except Exception:
            return None

    def audit(self, tool, args, envelope):
        audit.write(self.audit_path, self.user(), self.project_info(), tool, args, envelope)
