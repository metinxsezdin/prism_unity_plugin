import unittest

from fakes import FakeCore
from unity_bridge.protocol import BridgeError


class OpenUnity:
    def __init__(self, *outcomes, binding=None):
        self.outcomes = list(outcomes)
        self.binding = binding
        self.calls = []

    def call(self, cmd, args=None, interactive=False, timeout=None):
        self.calls.append((cmd, dict(args or {})))
        if cmd == "getSceneBinding":
            return self.binding
        if cmd == "getProjectInfo":
            return {"productGuid": "abc"}
        if cmd == "saveSceneTo":
            return {"workingPath": "Assets/x.unity"}
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class AskCore(FakeCore):
    def __init__(self, *answers):
        super().__init__()
        self.answers = list(answers)

    def popupQuestion(self, text, title=None, buttons=None, **kwargs):
        self.popups.append(text)
        return self.answers.pop(0)


UNSAVED = BridgeError("needs_confirmation", "The scene has unsaved changes.", {"reason": "unsaved_changes"})
FOREIGN = BridgeError("needs_confirmation", "Saved from another Unity project.", {"reason": "foreign_project"})


def plugin(core, unity):
    import prism_env  # noqa: F401
    from Prism_Unity_Functions import Prism_Unity_Functions

    funcs = Prism_Unity_Functions(core, None)
    funcs.unity = unity
    return funcs


class SceneOpenTests(unittest.TestCase):
    def test_open_interactive_asks_on_unsaved(self):
        core = AskCore("Discard")
        unity = OpenUnity(UNSAVED, {"workingPath": "Assets/Scenes/MeditationRoom/layout.unity"})
        self.assertTrue(plugin(core, unity).openScene(None, "P:/v0001.unity"))
        opens = [a for c, a in unity.calls if c == "openSceneFrom"]
        self.assertEqual(opens[0]["unsaved"], "abort")
        self.assertEqual(opens[1]["unsaved"], "discard")
        self.assertEqual(opens[1]["path"], "P:/v0001.unity")

    def test_open_interactive_save_version_then_retry(self):
        # "Save" means: keep the work as a Prism version first, then open the old version.
        unversioned = BridgeError("needs_confirmation", "Unversioned work.", {"reason": "unversioned_changes"})
        core = AskCore("Save version")
        unity = OpenUnity(unversioned, {"workingPath": "Assets/x.unity"})
        funcs = plugin(core, unity)
        saved = []
        funcs._save_version_before_open = lambda path: saved.append(path) or True
        self.assertTrue(funcs.openScene(None, "P:/v0001.unity"))
        self.assertEqual(saved, ["P:/v0001.unity"])
        opens = [a for c, a in unity.calls if c == "openSceneFrom"]
        self.assertEqual([a["unsaved"] for a in opens], ["abort", "abort"])

    def test_open_interactive_discard_unversioned(self):
        unversioned = BridgeError("needs_confirmation", "Unversioned work.", {"reason": "unversioned_changes"})
        core = AskCore("Discard")
        unity = OpenUnity(unversioned, {"workingPath": "Assets/x.unity"})
        self.assertTrue(plugin(core, unity).openScene(None, "P:/v0001.unity"))
        opens = [a for c, a in unity.calls if c == "openSceneFrom"]
        self.assertEqual(opens[1]["unsaved"], "discard")

    def test_open_interactive_cancel(self):
        core = AskCore("Cancel")
        unity = OpenUnity(UNSAVED)
        self.assertFalse(plugin(core, unity).openScene(None, "P:/v0001.unity"))
        self.assertEqual(len([c for c, a in unity.calls if c == "openSceneFrom"]), 1)

    def test_open_interactive_confirms_foreign_project(self):
        core = AskCore("Open anyway")
        unity = OpenUnity(FOREIGN, {"workingPath": "Assets/x.unity"})
        self.assertTrue(plugin(core, unity).openScene(None, "P:/v0001.unity"))
        opens = [a for c, a in unity.calls if c == "openSceneFrom"]
        self.assertTrue(opens[1]["confirmForeign"])

    def test_open_headless_propagates_needs_confirmation(self):
        core = AskCore()
        core.prismArgs.append("silent")
        unity = OpenUnity(UNSAVED)
        with self.assertRaises(BridgeError) as ctx:
            plugin(core, unity).openScene(None, "P:/v0001.unity")
        self.assertEqual(ctx.exception.code, "needs_confirmation")
        self.assertEqual(core.popups, [])

    def test_save_scene_records_target_in_version_info(self):
        core = AskCore()
        binding = {"entity": {"type": "asset", "asset_path": "Scenes/MeditationRoom"}, "department": "Unity", "task": "layout"}
        unity = OpenUnity(binding=binding)
        details = {}
        plugin(core, unity).saveScene(None, "P:/v0001.unity", details)
        self.assertEqual(details["type"], "asset")
        self.assertEqual(details["asset_path"], "Scenes/MeditationRoom")
        self.assertEqual(details["department"], "Unity")
        self.assertEqual(details["task"], "layout")
        self.assertEqual(details["unityProductGuid"], "abc")


if __name__ == "__main__":
    unittest.main()
