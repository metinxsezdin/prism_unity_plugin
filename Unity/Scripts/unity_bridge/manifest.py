"""Adding and removing the com.prism.unity package in a Unity project's Packages/manifest.json."""

import json
import shutil
import os
from collections import OrderedDict

PACKAGE_NAME = "com.prism.unity"


def is_unity_project(path):
    return os.path.isfile(os.path.join(path, "ProjectSettings", "ProjectVersion.txt")) and os.path.isfile(
        os.path.join(path, "Packages", "manifest.json")
    )


def _manifest_path(project_path):
    if not is_unity_project(project_path):
        raise ValueError("Not a Unity project folder: %s" % project_path)
    return os.path.join(project_path, "Packages", "manifest.json")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=OrderedDict)


def _write(path, data):
    tmp = path + ".prismtmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _to_forward(path):
    return os.path.abspath(path).replace("\\", "/")


def add_package(project_path, package_dir):
    """Point com.prism.unity at package_dir. Returns True when the manifest changed."""
    path = _manifest_path(project_path)
    data = _read(path)
    deps = data.get("dependencies") or OrderedDict()
    entry = "file:" + _to_forward(package_dir)
    if deps.get(PACKAGE_NAME) == entry:
        return False
    new_deps = OrderedDict([(PACKAGE_NAME, entry)])
    new_deps.update((k, v) for k, v in deps.items() if k != PACKAGE_NAME)
    data["dependencies"] = new_deps
    _write(path, data)
    return True


def remove_package(project_path):
    """Remove com.prism.unity. Returns True when the manifest changed."""
    path = _manifest_path(project_path)
    data = _read(path)
    deps = data.get("dependencies") or OrderedDict()
    if PACKAGE_NAME not in deps:
        return False
    del deps[PACKAGE_NAME]
    _write(path, data)
    return True


EMBEDDED_PACKAGES = ("com.prism.unity", "com.prism.assets")


def install_embedded(project_path, plugin_dir):
    """Copy the Prism packages into <project>/Packages so the project carries them (and Git shares them).

    Replaces an existing copy, and removes v1's machine-specific "file:" manifest entries.
    Returns the names of the packages installed.
    """
    path = _manifest_path(project_path)
    installed = []
    for name in EMBEDDED_PACKAGES:
        source = os.path.join(plugin_dir, "UnityPackage", name)
        if not os.path.isfile(os.path.join(source, "package.json")):
            continue
        target = os.path.join(project_path, "Packages", name)
        if os.path.isdir(target):
            shutil.rmtree(target)
        shutil.copytree(source, target)
        installed.append(name)

    data = _read(path)
    deps = data.get("dependencies") or OrderedDict()
    if any(name in deps for name in EMBEDDED_PACKAGES):
        data["dependencies"] = OrderedDict((k, v) for k, v in deps.items() if k not in EMBEDDED_PACKAGES)
        _write(path, data)
    return installed


def remove_embedded(project_path):
    """Remove the embedded Prism packages. Returns True when something was removed."""
    _manifest_path(project_path)
    removed = False
    for name in EMBEDDED_PACKAGES:
        target = os.path.join(project_path, "Packages", name)
        if os.path.isdir(target):
            shutil.rmtree(target)
            removed = True
    return removed


def write_project_binding(project_path, prism_project_config):
    """Pin the Prism project for this Unity project (ProjectSettings/PrismUnity/project.json)."""
    folder = os.path.join(project_path, "ProjectSettings", "PrismUnity")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "project.json")
    _write(path, OrderedDict([("prismProjectConfig", prism_project_config.replace("\\", "/"))]))
