"""Pinning the Prism project for one Unity project without changing the user's global choice."""

import os


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
    previous = core.getConfig("globals", "current project")
    try:
        core.changeProject(config_path, writeToConfig=False)
    finally:
        if previous and core.getConfig("globals", "current project") != previous:
            core.setConfig("globals", "current project", previous)
