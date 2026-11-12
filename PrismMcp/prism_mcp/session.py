"""One Prism core per server process, loaded on first use, never showing a window."""

import contextlib
import os

from unity_bridge.headless import headless
from unity_bridge.protocol import BridgeError

from . import audit, prefs

TEAM_PRISM_VERSION = "v2.1.2.1"


@contextlib.contextmanager
def _no_modal_dialogs():
    """Some Prism code opens a QMessageBox/QDialog with exec_() itself, past core.popup; offscreen that blocks forever."""
    try:
        from qtpy import QtWidgets
    except Exception:
        yield
        return

    def refuse(self, *args, **kwargs):
        text = ""
        try:
            text = self.text()
        except Exception:
            pass
        raise BridgeError("needs_input", "Prism wanted to ask: %s" % (text or "a question in a window"))

    saved = []
    for cls in (QtWidgets.QDialog, QtWidgets.QMessageBox):
        for name in ("exec_", "exec"):
            if name in vars(cls):
                saved.append((cls, name, vars(cls)[name]))
                setattr(cls, name, refuse)
    try:
        yield
    finally:
        for cls, name, original in saved:
            setattr(cls, name, original)


NO_USER = "No Prism user name is set. Open Prism once and enter your name."


def require_user_name():
    """Stop before Prism starts when the user has no Prism name: PrismCore would silently save the Windows login as it."""
    if os.environ.get("PRISM_USERNAME"):
        return
    if not ((prefs.user_config().get("globals") or {}).get("username") or "").strip():
        raise BridgeError("needs_input", NO_USER, {"missing": ["prismUser"]})


def create_core():
    """Load PrismCore without UI. Prism needs a Qt application; it is created offscreen."""
    require_user_name()
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
        self.audit_path = audit_path or audit.default_path()

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

    def begin_call(self):
        """Start of a tool call: forget Prism's cached config files, so teammates' changes are seen.

        Prism caches every config it reads for the life of the process and never checks the files again.
        """
        configs = getattr(self._core, "configs", None)
        if configs is not None and hasattr(configs, "clearCache"):
            configs.clearCache()

    def run(self, fn):
        """fn(core) with every Prism dialog turned into an error."""
        core = self.core
        with headless(core), _no_modal_dialogs():
            return fn(core)

    def project_info(self):
        core = self._core
        if core is None or not getattr(core, "prismIni", ""):
            return None
        return {"name": getattr(core, "projectName", ""), "path": (getattr(core, "projectPath", "") or "").replace("\\", "/")}

    def project_problem(self):
        """Why no project is active although the user has one: its drive is not reachable. None otherwise."""
        core = self.core
        if getattr(core, "prismIni", ""):
            return None
        wanted = core.getConfig("globals", "current project") or ""
        if wanted and not os.path.isfile(wanted):
            return "Your Prism project %s is not reachable (is the drive connected?). Connect it, or pick another project with set_project." % wanted.replace("\\", "/")
        return None

    def require_project(self):
        core = self.core
        if not getattr(core, "prismIni", ""):
            problem = self.project_problem()
            if problem:
                raise BridgeError("source_unavailable", problem, {"path": core.getConfig("globals", "current project")})
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
