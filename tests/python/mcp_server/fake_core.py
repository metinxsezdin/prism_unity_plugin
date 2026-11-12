"""A small stand-in for PrismCore, for the Prism MCP unit tests. Later tasks add to it."""

import os
import tempfile


class FakeUsers(object):
    def __init__(self, core):
        self.core = core

    def getUser(self):
        return self.core.getConfig("globals", "username")

    def getUserAbbreviation(self, userName=None, fromConfig=True):
        return self.core.getConfig("globals", "username_abbreviation") or (userName or "")[:3].lower()

    def ensureUser(self, *args, **kwargs):
        return True


class FakeProjects(object):
    def __init__(self, core):
        self.core = core
        self.recent = []  # [{"configPath", "name"}]

    def getRecentProjects(self, includeCurrent=False):
        return [dict(p) for p in self.recent if includeCurrent or p["configPath"] != self.core.prismIni]

    def ensureProject(self, *args, **kwargs):
        return True


class FakeCore(object):
    """Holds a temp folder per project; make_project() creates <root>/<name>/00_Pipeline/pipeline.json."""

    def __init__(self, root=None):
        self.root = root or tempfile.mkdtemp(prefix="prism_mcp_fake_")
        self.prismArgs = ["noUI"]
        self.version = "v2.1.2.1"
        self.config = {"globals": {"username": "Ayse Kaya", "username_abbreviation": "aka", "current project": ""}}
        self.prismIni = ""
        self.projectName = ""
        self.projectPath = ""
        self.useLocalFiles = False
        self.popups = []
        self.users = FakeUsers(self)
        self.projects = FakeProjects(self)
        self.changeProjectCalls = []

    # --- config ---------------------------------------------------------------
    def getConfig(self, cat=None, param=None, configPath=None, config=None, dft=None, location=None):
        if configPath:
            if cat == "globals" and param == "project_name":
                return os.path.basename(os.path.dirname(os.path.dirname(configPath)))
            return dft
        value = self.config.get(cat, {}).get(param) if param else self.config.get(cat)
        return dft if value is None else value

    def setConfig(self, cat=None, param=None, val=None, configPath=None, config=None, **kwargs):
        self.config.setdefault(cat, {})[param] = val

    # --- projects -------------------------------------------------------------
    def make_project(self, name, current=False, recent=True):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.join(path, "00_Pipeline"), exist_ok=True)
        cfg = os.path.join(path, "00_Pipeline", "pipeline.json")
        with open(cfg, "w") as f:
            f.write("{}")
        if recent:
            self.projects.recent.append({"configPath": cfg, "name": name})
        if current:
            self._activate(cfg)
            self.config["globals"]["current project"] = cfg
        return cfg

    def _activate(self, cfg):
        self.prismIni = cfg
        self.projectPath = os.path.dirname(os.path.dirname(cfg))
        self.projectName = os.path.basename(self.projectPath)

    def changeProject(self, configPath=None, openUi="", settingsTab=None, settingsType=None, unset=False, writeToConfig=None):
        self.changeProjectCalls.append((configPath, writeToConfig))
        self._activate(configPath)
        if writeToConfig:
            self.config["globals"]["current project"] = configPath
        return self.projectPath

    # --- dialogs (headless() replaces these; a call that reaches them is a bug) ---
    def popup(self, text, *args, **kwargs):
        self.popups.append(("popup", text))

    def popupQuestion(self, text, *args, **kwargs):
        self.popups.append(("popupQuestion", text))
        return kwargs.get("default")

    def writeErrorLog(self, text, *args, **kwargs):
        self.popups.append(("error", text))

    # --- paths ----------------------------------------------------------------
    def getEntityPath(self, entity=None, **kwargs):
        if entity.get("type") == "asset":
            return os.path.join(self.projectPath, "03_Production", "Assets", *entity["asset_path"].split("/"))
        return os.path.join(self.projectPath, "03_Production", "Shots", entity["sequence"], entity["shot"])


def make_session(core):
    """A Session around a fake core, with its audit log in the fake core's temp folder."""
    from prism_mcp.session import Session

    return Session(core_factory=lambda: core, audit_path=os.path.join(core.root, "audit.log"))


def call(session, _tool, **args):
    """Call a registered tool; returns the envelope. (_tool, so that tools can take a `name` argument.)"""
    from prism_mcp import registry

    return registry.call_tool(session, _tool, args)[0]
