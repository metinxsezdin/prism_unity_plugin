import unittest

from fakes import FakeCore
from unity_bridge import dialogs
from unity_bridge.protocol import BridgeError


class ScriptedUnity:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def call(self, cmd, args=None, interactive=False, timeout=None):
        self.calls.append((cmd, dict(args or {}), interactive))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class AnswerCore(FakeCore):
    def __init__(self, answer):
        super().__init__()
        self.answer = answer

    def popupQuestion(self, text, title=None, buttons=None, **kwargs):
        self.popups.append(text)
        return self.answer


class Cmds:
    def __init__(self, core, unity):
        self.core, self.unity = core, unity


BREAKING = BridgeError("needs_confirmation", "The new version renames objects.",
                       {"removedNodes": ["Stem"], "addedNodes": ["StemMain"], "removedMaterials": ["StemMat"]})


class DialogFlowTests(unittest.TestCase):
    def test_success_needs_no_question(self):
        cmds = Cmds(AnswerCore(dialogs.CANCEL), ScriptedUnity({"updated": False}))
        self.assertEqual(dialogs.run_import(cmds, "importProduct", {"product": "lotus_model"}), {"updated": False})
        self.assertEqual(cmds.core.popups, [])
        self.assertTrue(cmds.unity.calls[0][2], "menu imports are interactive")

    def test_breaking_update_confirmed_retries_with_confirm(self):
        cmds = Cmds(AnswerCore(dialogs.UPDATE_ANYWAY), ScriptedUnity(BREAKING, {"updated": True}))
        self.assertEqual(dialogs.run_import(cmds, "updateProduct", {"recordId": "x", "version": "v0003"}), {"updated": True})
        self.assertEqual(len(cmds.unity.calls), 2)
        self.assertNotIn("confirm", cmds.unity.calls[0][1])
        self.assertTrue(cmds.unity.calls[1][1]["confirm"])
        self.assertIn("Stem", cmds.core.popups[0])
        self.assertIn("StemMat", cmds.core.popups[0])

    def test_breaking_update_cancelled_does_not_retry(self):
        cmds = Cmds(AnswerCore(dialogs.CANCEL), ScriptedUnity(BREAKING))
        self.assertIsNone(dialogs.run_import(cmds, "updateProduct", {"recordId": "x"}))
        self.assertEqual(len(cmds.unity.calls), 1)

    def test_other_errors_are_shown(self):
        cmds = Cmds(AnswerCore(dialogs.CANCEL), ScriptedUnity(BridgeError("source_unavailable", "M: is offline")))
        self.assertIsNone(dialogs.run_import(cmds, "importProduct", {}))
        self.assertEqual(cmds.core.popups, ["M: is offline"])

    def test_import_args_carry_resolved_version(self):
        class Resolving(Cmds):
            def resolveVersion(self, entity, product, version="latest"):
                return {"version": "v0002", "filepath": "C:/p/v0002/lotus_v2.fbx", "location": "global"}

        cmds = Resolving(AnswerCore(dialogs.CANCEL), ScriptedUnity({"updated": False}))
        args = dialogs.import_args(cmds, {"type": "asset", "asset_path": "Props/Lotus"}, "lotus_model", "v0002")
        self.assertEqual(args["resolved"]["filepath"], "C:/p/v0002/lotus_v2.fbx")
        self.assertEqual(args["product"], "lotus_model")
        self.assertEqual(args["version"], "v0002")

    def test_entity_from_product_data(self):
        data = {"type": "asset", "asset_path": "Props/Lotus", "product": "lotus_model", "version": "v0002", "user": "adm"}
        self.assertEqual(dialogs.entity_from_product_data(data), {"type": "asset", "asset_path": "Props/Lotus"})


if __name__ == "__main__":
    unittest.main()
