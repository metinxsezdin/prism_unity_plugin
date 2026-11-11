"""Pinning the Prism project for one Unity project without changing the user's global choice."""

import contextlib
import os
import sys
import threading

_LOCAL_LOCK = threading.Lock()


@contextlib.contextmanager
def _project_switch_lock(timeout_sec=30):
    """Serialize read → changeProject → restore across Prism processes (and threads)."""
    with _LOCAL_LOCK:
        if sys.platform != "win32":
            yield
            return
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel32.CreateMutexW(None, False, "Local\\PrismUnity_ProjectSwitch")
        acquired = kernel32.WaitForSingleObject(handle, int(timeout_sec * 1000)) in (0, 0x80)  # signaled / abandoned
        try:
            yield
        finally:
            if acquired:
                kernel32.ReleaseMutex(handle)
            kernel32.CloseHandle(handle)


def _norm(path):
    return os.path.normcase(os.path.abspath(path)) if path else ""


def pin_project(core, config_path):
    """Make config_path the active project of this Prism process only.

    Prism's changeProject writes globals/current project whenever a UI is available, even with
    writeToConfig=False. That setting is what Maya, Blender and Prism itself open next, so it is
    restored right after the switch.
    """
    if not config_path or _norm(getattr(core, "prismIni", "")) == _norm(config_path):
        return
    with _project_switch_lock():
        previous = core.getConfig("globals", "current project")
        try:
            core.changeProject(config_path, writeToConfig=False)
        finally:
            if previous and core.getConfig("globals", "current project") != previous:
                core.setConfig("globals", "current project", previous)
