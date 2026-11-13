"""A small stand-in for PrismCore, for the Prism MCP unit tests. Later tasks add to it."""

import copy
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

    def getAssetDepartments(self):
        return FakeEntities.DEPARTMENTS["asset"]

    def getShotDepartments(self):
        return FakeEntities.DEPARTMENTS["shot"]

    def getAssetTaskPresets(self):
        return FakeEntities.PRESETS["asset"]

    def getShotTaskPresets(self):
        return FakeEntities.PRESETS["shot"]

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
        self.localProjectPath = ""
        self.popups = []
        self.users = FakeUsers(self)
        self.projects = FakeProjects(self)
        self.changeProjectCalls = []
        self.shotinfo = {}  # Prism's shotinfo config: {"shotRanges": {seq: {shot: [s, e]}}, "shots": {seq: {shot: {...}}}}

    # --- config ---------------------------------------------------------------
    def getConfig(self, cat=None, param=None, configPath=None, config=None, dft=None, location=None, **kwargs):
        if config == "shotinfo":
            value = copy.deepcopy(self.shotinfo.get(cat) if cat else self.shotinfo)
            return dft if value is None else value
        if configPath:
            if cat == "globals" and param == "project_name":
                return os.path.basename(os.path.dirname(os.path.dirname(configPath)))
            return dft
        value = self.config.get(cat, {}).get(param) if param else self.config.get(cat)
        return dft if value is None else value

    def setConfig(self, cat=None, param=None, val=None, configPath=None, config=None, data=None, **kwargs):
        if config == "shotinfo":
            if data is not None:
                self.shotinfo = copy.deepcopy(data)
            else:
                self.shotinfo.setdefault(cat, {})[param] = copy.deepcopy(val)
            return
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
    def getEntityPath(self, entity=None, step=None, category=None, **kwargs):
        if entity.get("type") == "asset":
            base = os.path.join(self.projectPath, "03_Production", "Assets", *entity["asset_path"].split("/"))
        elif entity.get("type") == "sequence":
            return os.path.join(self.projectPath, "03_Production", "Shots", entity["sequence"])
        else:
            base = os.path.join(self.projectPath, "03_Production", "Shots", entity["sequence"], entity["shot"])
        if step:
            base = os.path.join(base, "Scenefiles", step)
            if category:
                base = os.path.join(base, category)
        return base


def make_session(core):
    """A Session around a fake core, with its audit log in the fake core's temp folder."""
    from prism_mcp.session import Session

    return Session(core_factory=lambda: core, audit_path=os.path.join(core.root, "audit.log"))


def call(session, _tool, **args):
    """Call a registered tool; returns the envelope. (_tool, so that tools can take a `name` argument.)"""
    from prism_mcp import registry

    return registry.call_tool(session, _tool, args)[0]


# --- entities, products, media (Task 3+) ------------------------------------------


def entity_label(entity):
    if entity.get("type") == "asset":
        return entity["asset_path"].replace("\\", "/")
    return "%s/%s" % (entity.get("sequence"), entity.get("shot"))


class FakeEntities(object):
    """In-memory project contents; add_asset/add_shot also create the entity folder."""

    def __init__(self, core):
        self.core = core
        self.assets = []
        self.shots = []
        self.omitted = set()
        self.steps = {}  # label -> {department: [tasks]}
        self.scenefiles = []  # (label, department, task, path, data)
        self.descriptions = {}  # asset name -> text
        self.metadata = {}  # asset label -> dict (shots keep theirs in core.shotinfo, like Prism)
        self.deps = {}  # scenefile path -> [paths]

    def add_asset(self, path, omitted=False):
        self.assets.append(path)
        os.makedirs(self.core.getEntityPath(entity={"type": "asset", "asset_path": path}), exist_ok=True)
        if omitted:
            self.omitted.add(path)

    def add_shot(self, sequence, shot, frame_range=None):
        self.shots.append((sequence, shot))
        os.makedirs(self.core.getEntityPath(entity={"type": "shot", "sequence": sequence, "shot": shot}), exist_ok=True)
        if frame_range:
            self.setShotRange({"type": "shot", "sequence": sequence, "shot": shot}, *frame_range)

    @property
    def ranges(self):
        """label -> [start, end], read from the shotinfo config."""
        out = {}
        for seq, shots in (self.core.shotinfo.get("shotRanges") or {}).items():
            for shot, frames in shots.items():
                out["%s/%s" % (seq, shot)] = list(frames)
        return out

    def add_scenefile(self, entity, department, task, filename, version="v0001", comment="", user="aka", deps=()):
        folder = os.path.join(self.core.getEntityPath(entity=entity), "Scenefiles", department, task)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        with open(path, "w") as f:
            f.write("scene")
        data = dict(entity, department=department, task=task, version=version, comment=comment, user=user,
                    extension=os.path.splitext(filename)[1], filename=path)
        self.scenefiles.append((entity_label(entity), department, task, path, data))
        self.steps.setdefault(entity_label(entity), {}).setdefault(department, [])
        if task not in self.steps[entity_label(entity)][department]:
            self.steps[entity_label(entity)][department].append(task)
        self.deps[path] = list(deps)
        return path

    def getAssets(self, path=None, depth=0, includeOmitted=False):
        return [{"type": "asset", "asset_path": a.replace("/", "\\")} for a in self.assets if includeOmitted or a not in self.omitted]

    def getShots(self, searchFilter="", locations=None, episode=None, sequence=None, includeOmitted=False):
        out = []
        for seq, shot in self.shots:
            if not includeOmitted and "%s/%s" % (seq, shot) in self.omitted:
                continue
            out.append({"type": "shot", "sequence": seq, "shot": shot})
        return out

    def isEntityOmitted(self, entity):
        return entity_label(entity) in self.omitted

    def getSteps(self, entity):
        return list(self.steps.get(entity_label(entity), {}))

    def getCategories(self, entity, step=None):
        return list(self.steps.get(entity_label(entity), {}).get(step, []))

    def getScenefiles(self, entity=None, step=None, category=None, extensions=None, path=None):
        return [p for (lbl, dep, task, p, _) in self.scenefiles
                if lbl == entity_label(entity) and step in (None, dep) and category in (None, task)]

    def getScenefileData(self, fileName, preview=False, getEntityFromPath=False):
        for (_, _, _, p, data) in self.scenefiles:
            if p == fileName:
                return dict(data)
        return {"filename": fileName}

    def getAssetNameFromPath(self, path):
        return os.path.basename(path.replace("\\", "/").rstrip("/"))

    def getAssetDescription(self, assetName, projectPath=None):
        return self.descriptions.get(assetName, "")

    def getMetaData(self, entity, projectPath=None):
        if entity.get("type") == "shot":
            shots = self.core.shotinfo.get("shots") or {}
            return dict(shots.get(entity["sequence"], {}).get(entity["shot"], {}).get("metadata", {}))
        return dict(self.metadata.get(entity_label(entity), {}))

    def getEntityPreviewPath(self, entity):
        return os.path.join(self.core.projectPath, "00_Pipeline", "Assetinfo", os.path.basename(entity_label(entity)) + "_preview.jpg")

    def getShotRange(self, entity, handles=False):
        frames = (self.core.shotinfo.get("shotRanges") or {}).get(entity.get("sequence"), {}).get(entity.get("shot"))
        return list(frames) if frames else None

    def getDependencies(self, path):
        return list(self.deps.get(path, []))

    # --- creation (Task 5) --------------------------------------------------------
    DEPARTMENTS = {
        "asset": [{"name": "Modeling", "abbreviation": "mod", "defaultTasks": ["Modeling"]},
                  {"name": "Surfacing", "abbreviation": "surf", "defaultTasks": ["Surfacing"]}],
        "shot": [{"name": "Animation", "abbreviation": "anm", "defaultTasks": ["Animation"]}],
    }
    PRESETS = {"asset": [{"name": "Prop", "departments": [{"name": "Modeling", "tasks": ["Sculpt", "Retopo"]},
                                                           {"name": "Surfacing", "tasks": ["Surfacing"]}]}],
               "shot": []}

    def getTypeFromAssetPath(self, path, content=None):
        if not os.path.exists(path):
            return None
        for a in self.assets:
            if os.path.normcase(self.core.getEntityPath(entity={"type": "asset", "asset_path": a})) == os.path.normcase(os.path.normpath(path)):
                return "asset"
        return "folder"

    def isValidAssetName(self, assetName):
        return assetName not in ("Export", "Scenefiles", "Playblasts")

    def createEntity(self, entity, dialog=None, frameRange=None, silent=False, description=None, preview=None, metaData=None):
        if entity["type"] == "asset" and not self.isValidAssetName(self.getAssetNameFromPath(entity["asset_path"])):
            self.core.popupQuestion("Invalid asset name. Continue anyway?")
            return {}
        if entity["type"] == "asset":
            self.add_asset(entity["asset_path"])
            if description:
                self.descriptions[self.getAssetNameFromPath(entity["asset_path"])] = description
        else:
            self.add_shot(entity["sequence"], entity["shot"], frame_range=frameRange)
        return {"entity": entity, "existed": False}

    def _deps(self, entity_type):
        return self.DEPARTMENTS["asset" if entity_type == "asset" else "shot"]

    def getDepartmentAbbreviation(self, entity, department):
        return next((d["abbreviation"] for d in self._deps(entity) if d["name"] == department), None)

    def getLongDepartmentName(self, entity, abbreviation):
        return next((d["name"] for d in self._deps(entity) if d["abbreviation"] == abbreviation), None)

    def getDefaultTasksForDepartment(self, entity, department):
        return next((list(d["defaultTasks"]) for d in self._deps(entity) if d["abbreviation"] == department), None)

    def createDepartment(self, department, entity, stepPath="", createCat=True):
        path = self.core.getEntityPath(entity=entity, step=department)
        os.makedirs(path, exist_ok=True)
        self.steps.setdefault(entity_label(entity), {}).setdefault(department, [])
        if createCat:
            for task in self.getDefaultTasksForDepartment(entity["type"], department) or []:
                self.createCategory(entity, department, task)
        return path

    def createCategory(self, entity, step, category):
        path = self.core.getEntityPath(entity=entity, step=step, category=category)
        os.makedirs(path, exist_ok=True)
        tasks = self.steps.setdefault(entity_label(entity), {}).setdefault(step, [])
        if category not in tasks:
            tasks.append(category)
        return path

    def createTasksFromPreset(self, entity, preset=None, presetName=None):
        preset = preset or next(p for p in self.PRESETS[entity["type"]] if p["name"] == presetName)
        paths = []
        for dep in preset["departments"]:
            abbr = self.getDepartmentAbbreviation(entity["type"], dep["name"])
            self.createDepartment(abbr, entity, createCat=False)
            for task in dep["tasks"]:
                paths.append(self.createCategory(entity, abbr, task))
        return paths

    def setAssetDescription(self, assetName, description):
        self.descriptions[assetName] = description

    def setMetaData(self, entity=None, metaData=None, entities=None, metaDatas=None):
        if entity.get("type") == "shot":
            shots = self.core.shotinfo.setdefault("shots", {})
            shots.setdefault(entity["sequence"], {}).setdefault(entity["shot"], {})["metadata"] = dict(metaData)
            return
        self.metadata[entity_label(entity)] = dict(metaData)

    def setShotRange(self, entity, start, end):
        ranges = self.core.shotinfo.setdefault("shotRanges", {})
        ranges.setdefault(entity["sequence"], {})[entity["shot"]] = [start, end]

    def setComment(self, filepath, comment):
        for (_, _, _, p, data) in self.scenefiles:
            if p == filepath:
                data["comment"] = comment
        return filepath

    def omitEntity(self, entity, omit=True):
        (self.omitted.add if omit else self.omitted.discard)(entity_label(entity))

    # --- rename / delete (Task 7) --------------------------------------------------
    fail_rename_after_first = False

    def _locations(self, path):
        out = [path]
        if self.core.useLocalFiles:
            out.append(path.replace(self.core.projectPath, self.core.localProjectPath))
        return out

    def _rename_folders(self, old, new):
        for i, (src, dst) in enumerate(zip(self._locations(old), self._locations(new))):
            if i == 1 and self.fail_rename_after_first:
                from unity_bridge.protocol import BridgeError
                raise BridgeError("needs_input", "Permission denied. Another programm uses files in the shotfolder.")
            if os.path.exists(src):
                os.rename(src, dst)

    def renameShot(self, curShotData, newShotData, locations=None):
        self._rename_folders(self.core.getEntityPath(entity=curShotData), self.core.getEntityPath(entity=newShotData))
        self.shots = [(s, newShotData["shot"]) if (s, h) == (curShotData["sequence"], curShotData["shot"]) else (s, h) for s, h in self.shots]

    def renameSequence(self, curSeqName, newSeqName, locations=None):
        self._rename_folders(self.core.getEntityPath(entity={"type": "sequence", "sequence": curSeqName}),
                             self.core.getEntityPath(entity={"type": "sequence", "sequence": newSeqName}))
        self.shots = [(newSeqName if s == curSeqName else s, h) for s, h in self.shots]

    def deleteShot(self, shotName):
        raise AssertionError("the MCP must never call Prism's deleteShot (it loops forever on a locked file in noUI mode)")

    def setEntityPreview(self, entity, pixmap, width=250, height=141):
        path = self.getEntityPreviewPath(entity)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("jpg")
        return pixmap


class FakeProducts(object):
    """Product versions as real folders: <entity>/Export/<product>/<version>/<product>_<version>.fbx."""

    def __init__(self, core):
        self.core = core
        self.products = {}  # label -> {product: [versions]}
        self.info = {}  # version folder -> {comment, user, date}
        self.masters = {}  # (label, product) -> content version

    def add_product(self, entity, product, versions, comments=None, master=None):
        label = entity_label(entity)
        self.products.setdefault(label, {})[product] = list(versions)
        for v in versions:
            folder = self._folder(entity, product, v)
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "%s_%s.fbx" % (product, v)), "w") as f:
                f.write("fbx")
            self.info[folder] = {"comment": (comments or {}).get(v, ""), "user": "aka", "date": "01.11.26 10:00:00"}
        if master:
            self.masters[(label, product)] = master

    def _folder(self, entity, product, version):
        return os.path.join(self.core.getEntityPath(entity=entity), "Export", product, version)

    def getProductsFromEntity(self, entity, locations=None):
        return [{"product": p} for p in self.products.get(entity_label(entity), {})]

    def getVersionsFromProduct(self, entity, product, locations="all"):
        label = entity_label(entity)
        out = []
        for v in self.products.get(label, {}).get(product, []):
            folder = self._folder(entity, product, v)
            out.append(dict(entity, product=product, version=v, path=folder, locations={"global": folder}))
        if (label, product) in self.masters:
            folder = self._folder(entity, product, "master")
            out.append(dict(entity, product=product, version="master", path=folder, locations={"global": folder}))
        return out

    def getVersionInfoFromVersion(self, version):
        if version.get("version") == "master":
            content = self.masters[(entity_label(version), version["product"])]
            return self.info.get(self._folder(version, version["product"], content), {})
        return self.info.get(version.get("path"), {})

    def getPreferredFileFromVersion(self, version):
        v = version["version"]
        if v == "master":
            v = self.masters[(entity_label(version), version["product"])]
        return os.path.join(self._folder(version, version["product"], v), "%s_%s.fbx" % (version["product"], v))

    def getMasterVersionNumber(self, masterPath, allowCache=True):
        norm = masterPath.replace("\\", "/")
        for (label, product), content in self.masters.items():
            if norm.endswith("%s/Export/%s/master" % (label, product)):
                return content
        return None

    def getProductPreviewPath(self, path):
        return ""

    # --- version management (Task 6) --------------------------------------------
    def _from_file(self, path):
        norm = path.replace("\\", "/")
        for label, products in self.products.items():
            for product, versions in products.items():
                for v in versions + ["master"]:
                    if "/%s/Export/%s/%s/" % (label, product, v) in norm:
                        return label, product, v
        return None, None, None

    def updateMasterVersion(self, path):
        label, product, version = self._from_file(path)
        if not version:
            return None
        self.masters[(label, product)] = version
        return path

    def deleteMasterVersion(self, path, errorMsg=None, allowClear=True, allowRename=True):
        label, product, _ = self._from_file(path)
        if getattr(self, "fail_delete", False):
            return False
        self.masters.pop((label, product), None)
        return True

    def setComment(self, versionPath, comment):
        self.info.setdefault(versionPath, {})["comment"] = comment


class FakeMedia(object):
    def __init__(self, core):
        self.core = core
        self.media = {}  # label -> {kind: {identifier: [version dicts]}}

    def add_media(self, entity, kind, identifier, versions):
        self.media.setdefault(entity_label(entity), {}).setdefault(kind, {})[identifier] = versions

    def getIdentifiersByType(self, entity, locations=None):
        kinds = {"3d": [], "2d": [], "playblast": [], "external": []}
        for kind, ids in self.media.get(entity_label(entity), {}).items():
            for identifier in ids:
                kinds[kind].append(dict(entity, identifier=identifier, mediaType=kind))
        return kinds

    def getVersionsFromIdentifier(self, identifier, locations=None):
        return [dict(v) for v in self.media[entity_label(identifier)][identifier["mediaType"]][identifier["identifier"]]]

    def _versions_of(self, version):
        for kinds in self.media.values():
            for ids in kinds.values():
                for vs in ids.values():
                    if any(v.get("path") == version.get("path") for v in vs):
                        return vs
        return None

    def getMasterVersionNumber(self, masterPath):
        for kinds in self.media.values():
            for ids in kinds.values():
                for vs in ids.values():
                    for v in vs:
                        if v.get("path") == masterPath and v["version"] == "master":
                            return v["content"]
        return None

    def updateMasterVersion(self, path=None, context=None, isFilepath=True, add=False, mediaType=None):
        vs = self._versions_of(context)
        vs[:] = [v for v in vs if v["version"] != "master"]
        vs.append({"version": "master", "content": context["version"], "path": context["path"] + "_master"})
        return context["path"] + "_master"

    def setComment(self, versionPath, comment):
        for kinds in self.media.values():
            for ids in kinds.values():
                for vs in ids.values():
                    for v in vs:
                        if v.get("path") == versionPath:
                            v["comment"] = comment


def make_project_core(name="Wellness"):
    """A FakeCore with an active project and empty entities/products/media."""
    core = FakeCore()
    core.make_project(name, current=True)
    core.entities = FakeEntities(core)
    core.products = FakeProducts(core)
    core.mediaProducts = FakeMedia(core)
    core.getScenefileData = core.entities.getScenefileData
    return core
