"""Running Prism without dialogs for calls that come from Claude (interactive=False)."""

import contextlib
import hashlib
import os
import sys

from .protocol import BridgeError


@contextlib.contextmanager
def headless(core):
    """Suppress Prism dialogs for the duration of a non-interactive command.

    Adds Prism's own "silent" flag and replaces core.popup / core.popupQuestion so
    that any attempt to ask the user becomes a needs_input error instead of a window.
    Everything is restored on exit, including when the body raises.
    """
    added_silent = "silent" not in core.prismArgs
    if added_silent:
        core.prismArgs.append("silent")
    def refuse(text, *args, **kwargs):
        raise BridgeError("needs_input", str(text), {"dialog": str(kwargs.get("title") or "")})

    def surface_error(text, *args, **kwargs):
        # Prism's err_catcher swallows exceptions and reports them through
        # writeErrorLog (a dialog). Re-raise instead so the caller gets the error.
        current = sys.exc_info()[1]
        if isinstance(current, BridgeError):
            raise current
        raise BridgeError("internal", str(text).strip().splitlines()[-1] if str(text).strip() else "Prism error")

    patches = {"popup": refuse, "popupQuestion": refuse}
    if hasattr(core, "writeErrorLog"):
        patches["writeErrorLog"] = surface_error
    saved = {name: (name in vars(core), getattr(core, name)) for name in patches}
    saved_error_time = getattr(core, "lastErrorTime", None)
    for name, fn in patches.items():
        setattr(core, name, fn)
    if saved_error_time is not None:
        core.lastErrorTime = 0
    try:
        yield
    finally:
        for name, (was_instance_attr, original) in saved.items():
            if was_instance_attr:
                setattr(core, name, original)
            else:
                delattr(core, name)
        if added_silent and "silent" in core.prismArgs:
            core.prismArgs.remove("silent")


def instance_key(unity_project_path):
    """Stable per-Unity-project key used for the single-instance mutex name."""
    norm = os.path.normcase(os.path.abspath(unity_project_path)).rstrip("\\/").lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]
