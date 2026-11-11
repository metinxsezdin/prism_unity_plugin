# -*- coding: utf-8 -*-
#
# Prism ↔ Unity integration: install / remove the com.prism.unity package in a Unity project.
#
# The "install path" Prism asks for is the Unity project root. Installing adds the package to
# Packages/manifest.json and pins the current Prism project in ProjectSettings/PrismUnity/project.json.

import os
import sys

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from unity_bridge import manifest


class Prism_Unity_Integration(object):
    def __init__(self, core, plugin):
        self.core = core
        self.plugin = plugin
        self.examplePath = None

    @property
    def packageDir(self):
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "UnityPackage", "com.prism.unity"
        )

    def getExecutable(self):
        return ""

    def _warn(self, text):
        parent = getattr(self.core, "messageParent", None)
        if QApplication.instance() is not None:
            QMessageBox.warning(parent, "Prism Integration", text)
        else:
            print(text)

    def addIntegration(self, installPath):
        try:
            if not manifest.is_unity_project(installPath):
                self._warn(
                    "This folder is not a Unity project:\n%s\n\n"
                    "Select the Unity project folder (the one that contains Assets, Packages and ProjectSettings)."
                    % installPath
                )
                return False
            manifest.add_package(installPath, self.packageDir)
            prism_project = getattr(self.core, "prismIni", "") or ""
            if prism_project:
                manifest.write_project_binding(installPath, prism_project)
            return True
        except Exception as e:
            self._warn("Errors occurred during the Unity integration.\n\n%s: %s" % (type(e).__name__, e))
            return False

    def removeIntegration(self, installPath):
        try:
            if manifest.is_unity_project(installPath):
                manifest.remove_package(installPath)
            return True
        except Exception as e:
            self._warn("Errors occurred during the removal of the Unity integration.\n\n%s: %s" % (type(e).__name__, e))
            return False

    def updateInstallerUI(self, userFolders, pItem):
        try:
            pluginItem = QTreeWidgetItem([self.plugin.pluginName])
            pItem.addChild(pluginItem)
            pluginItem.setCheckState(0, Qt.Unchecked)
            pluginItem.setText(1, "< doubleclick to browse to a Unity project folder >")
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self._warn("Errors occurred during the installation.\n\n%s\n%s\n%s" % (str(e), exc_type, exc_tb.tb_lineno))
            return False

    def installerExecute(self, pluginItem, result):
        try:
            installLocs = []
            if pluginItem.checkState(0) != Qt.Checked:
                return installLocs
            paths = []
            for i in range(pluginItem.childCount()):
                item = pluginItem.child(i)
                if item.checkState(0) == Qt.Checked and os.path.exists(item.text(1)):
                    paths.append(item.text(1))
            if not paths and os.path.exists(pluginItem.text(1)):
                paths.append(pluginItem.text(1))
            for path in paths:
                result["Unity integration"] = self.core.integration.addIntegration(self.plugin.pluginName, path=path, quiet=True)
                if result["Unity integration"]:
                    installLocs.append(path)
            return installLocs
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self._warn("Errors occurred during the installation.\n\n%s\n%s\n%s" % (str(e), exc_type, exc_tb.tb_lineno))
            return False
