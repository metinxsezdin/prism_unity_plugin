"""Running Prism without dialogs for calls that come from Claude (interactive=False)."""

import contextlib
import hashlib
import os

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
    had_popup = "popup" in vars(core)
    had_question = "popupQuestion" in vars(core)
    original_popup = core.popup
    original_question = core.popupQuestion

    def refuse(text, *args, **kwargs):
        raise BridgeError("needs_input", str(text), {"dialog": str(kwargs.get("title") or "")})

    core.popup = refuse
    core.popupQuestion = refuse
    try:
        yield
    finally:
        if had_popup:
            core.popup = original_popup
        else:
            del core.popup
        if had_question:
            core.popupQuestion = original_question
        else:
            del core.popupQuestion
        if added_silent and "silent" in core.prismArgs:
            core.prismArgs.remove("silent")


def instance_key(unity_project_path):
    """Stable per-Unity-project key used for the single-instance mutex name."""
    norm = os.path.normcase(os.path.abspath(unity_project_path)).rstrip("\\/").lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]
