import unittest

from fakes import FakeCore
from unity_bridge import protocol
from unity_bridge.commands import PrismCommands
from unity_bridge.protocol import BridgeError

ROOM = {"type": "asset", "asset_path": "Scenes/MeditationRoom"}


class SceneUnity:
    """Fake Unity: remembers the binding and the files Prism asked it to save."""

    def __init__(self, binding=None):
        self.binding = binding
        self.calls = []
        self.playing = False

    def call(self, cmd, args=None, interactive=False, timeout=None):
        self.calls.append((cmd, args))
        if cmd == "getSceneBinding":
            return self.binding
        if cmd == "bindScene":
            self.binding = {"sceneGuid": "g1", "workingPath": "Assets/Scenes/MeditationRoom/layout.unity",
                            "entity": args["entity"], "department": args["department"], "task": args["task"],
                            "lastPrismPath": None}
            return self.binding
        if cmd == "assertEditable":
            if self.playing:
                raise BridgeError("unity_busy", "Unity is in Play Mode")
            return True
        if cmd == "getProjectInfo":
            return {"projectPath": "C:/Proj", "productGuid": "abc-123"}
        if cmd == "saveSceneTo":
            self.binding["lastPrismPath"] = args["path"]
            return {"workingPath": self.binding["workingPath"]}
        raise AssertionError("unexpected Unity call " + cmd)


class Entities:
    def __init__(self, steps):
        self.steps = steps
        self.created = []

    def getSteps(self, entity):
        return list(self.steps)

    def getCategories(self, entity, step=None):
        return []

    def createDepartment(self, department, entity, stepPath="", createCat=True):
        self.created.append(("department", department))
        self.steps.append(department)
        return department

    def createCategory(self, entity, step, category):
        self.created.append(("category", category))
        return category


class SceneCore(FakeCore):
    def __init__(self, steps=("Unity",)):
        super().__init__()
        self.entities = Entities(list(steps))
        self.saved = []

    def generateScenePath(self, entity, department, task="", extension="", comment="", **kwargs):
        n = len(self.saved) + 1
        return "P:/Scenefiles/%s/%s/MeditationRoom_%s_v%04d_%s%s" % (department, task, task, n, comment, extension)

    def saveScene(self, comment="", filepath="", **kwargs):
        details = {}
        self.appPlugin.saveScene(self, filepath, details)
        self.saved.append((filepath, comment, details))
        return filepath

    def getScenefileData(self, path, **kwargs):
        return {"version": "v%04d" % len(self.saved)}


def plugin_for(core, unity):
    import prism_env  # noqa: F401
    from Prism_Unity_Functions import Prism_Unity_Functions

    funcs = Prism_Unity_Functions(core, None)
    funcs.unity = unity
    funcs.sceneFormats = [".unity"]  # from Prism_Unity_Variables in the real plugin
    return funcs


class SceneSaveTests(unittest.TestCase):
    def make(self, binding=None, steps=("Unity",)):
        core = SceneCore(steps)
        unity = SceneUnity(binding)
        core.appPlugin = plugin_for(core, unity)
        return core, unity, PrismCommands(core, unity)

    @staticmethod
    def call(cmds, cmd, **args):
        return cmds.dispatch(protocol.make_request(cmd, args, "t", False))

    def test_first_save_without_target_needs_input(self):
        core, unity, cmds = self.make()
        resp = self.call(cmds, "saveVersion", comment="ilk")
        self.assertEqual(resp["error"]["code"], "needs_input")
        self.assertEqual(resp["error"]["details"]["missing"], ["entity", "task"])
        self.assertEqual(core.saved, [])

    def test_first_save_binds_and_saves(self):
        core, unity, cmds = self.make()
        resp = self.call(cmds, "saveVersion", comment="ilk", entity=ROOM, task="layout")
        self.assertTrue(resp["ok"], resp)
        self.assertEqual(resp["result"]["version"], "v0001")
        self.assertEqual(unity.binding["department"], "Unity")
        path, comment, details = core.saved[0]
        self.assertIn("/Unity/layout/", path)
        self.assertTrue(path.endswith(".unity"))
        self.assertEqual(comment, "ilk")
        self.assertEqual(unity.binding["lastPrismPath"], path)

    def test_missing_department_needs_confirmation(self):
        core, unity, cmds = self.make(steps=())
        resp = self.call(cmds, "saveVersion", entity=ROOM, task="layout")
        self.assertEqual(resp["error"]["code"], "needs_confirmation")
        self.assertEqual(resp["error"]["details"]["department"], "Unity")
        self.assertEqual(core.entities.created, [])

    def test_create_department_true_creates_then_saves(self):
        core, unity, cmds = self.make(steps=())
        resp = self.call(cmds, "saveVersion", entity=ROOM, task="layout", createDepartment=True)
        self.assertTrue(resp["ok"], resp)
        self.assertIn(("department", "Unity"), core.entities.created)
        self.assertEqual(len(core.saved), 1)

    def test_play_mode_refused_before_any_prism_change(self):
        core, unity, cmds = self.make(steps=())
        unity.playing = True
        resp = self.call(cmds, "saveVersion", entity=ROOM, task="layout", createDepartment=True)
        self.assertEqual(resp["error"]["code"], "unity_busy")
        self.assertEqual(core.entities.created, [], "no department/category may be created in Play Mode")
        self.assertEqual(core.saved, [])

    def test_second_save_uses_binding(self):
        core, unity, cmds = self.make()
        self.call(cmds, "saveVersion", comment="ilk", entity=ROOM, task="layout")
        resp = self.call(cmds, "saveVersion", comment="ikinci")
        self.assertEqual(resp["result"]["version"], "v0002")
        self.assertIn("/Unity/layout/", core.saved[1][0])

    def test_get_current_file_name_uses_last_prism_path(self):
        core, unity, cmds = self.make(binding={"lastPrismPath": "P:/Scenefiles/Unity/layout/x_v0003_.unity"})
        self.assertEqual(core.appPlugin.getCurrentFileName(None), "P:/Scenefiles/Unity/layout/x_v0003_.unity")

    def test_get_current_file_name_empty_when_unbound(self):
        core, unity, cmds = self.make(binding=None)
        self.assertEqual(core.appPlugin.getCurrentFileName(None), "")

    def test_save_scene_adds_unity_product_guid(self):
        core, unity, cmds = self.make()
        self.call(cmds, "saveVersion", entity=ROOM, task="layout")
        self.assertEqual(core.saved[0][2]["unityProductGuid"], "abc-123")
        self.assertIn(("saveSceneTo", {"path": core.saved[0][0]}), unity.calls)


if __name__ == "__main__":
    unittest.main()
