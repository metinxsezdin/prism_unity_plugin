"""Test-only hooks, enabled by environment variables in Prism_Unity_Launcher.py.

PRISM_UNITY_FAIL_ON_DIALOG=1  every dialog that tries to open makes the current command fail with
                              an "internal" error naming the window, so E2E tests prove that
                              Claude-driven (interactive=False) calls never open a window.
"""

from .protocol import BridgeError


def install_fail_on_dialog(*classes):
    def make(name):
        def refuse(self, *args, **kwargs):
            try:
                title = self.windowTitle()
            except Exception:
                title = type(self).__name__
            raise BridgeError("internal", "A window tried to open during a test: %s (%s)" % (title, name))

        return refuse

    for cls in classes:
        for name in ("exec_", "exec", "show"):
            if hasattr(cls, name):
                setattr(cls, name, make(name))
