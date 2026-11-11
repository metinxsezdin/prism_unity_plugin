"""Product queries against the real Prism and the test Prism project.

Run: $env:PRISM_UNITY_IT=1; tools/run_py_tests.ps1 -Pattern "test_*_it.py"
Needs tools/make_test_prism_project.py to have created the test project.
"""

import os
import unittest

import prism_env

TEST_PROJECT = os.environ.get(
    "PRISM_UNITY_TEST_PROJECT",
    os.path.join(os.path.expanduser("~"), "PrismUnityTest Project", "00_Pipeline", "pipeline.json"),
)
LOTUS = {"type": "asset", "asset_path": "Props/Lotus"}
RUN = os.environ.get("PRISM_UNITY_IT") == "1" and prism_env.PRISM_AVAILABLE and os.path.exists(TEST_PROJECT)

_core = None


def core():
    global _core
    if _core is None:
        import PrismCore
        from qtpy.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
        _core = PrismCore.create(app="Standalone", prismArgs=["noUI", "silent"])
        from unity_bridge.projects import pin_project

        pin_project(_core, TEST_PROJECT)
    return _core


@unittest.skipUnless(RUN, "set PRISM_UNITY_IT=1 and create the test Prism project")
class ProductsIntegrationTests(unittest.TestCase):
    def setUp(self):
        from unity_bridge.commands import PrismCommands

        self.cmds = PrismCommands(core(), unity=None)

    def test_list_versions_and_resolve_latest(self):
        versions = self.cmds.listVersions(LOTUS, "lotus_model")
        self.assertEqual([v["version"] for v in versions], ["v0001", "v0002", "v0003"])
        self.assertEqual(versions[1]["comment"], "bigger petals")
        latest = self.cmds.resolveVersion(LOTUS, "lotus_model")
        self.assertEqual(latest["version"], "v0003")
        self.assertTrue(latest["filepath"].endswith("lotus_v3_renamed.fbx"))
        self.assertTrue(os.path.isfile(latest["filepath"]))

    def test_turkish_entity(self):
        latest = self.cmds.resolveVersion({"type": "asset", "asset_path": "Props/Çay Bardağı"}, "cay_model")
        self.assertEqual(latest["version"], "v0001")

    def test_users_current_project_untouched(self):
        import json

        with open(os.path.expanduser("~/Documents/Prism2/Prism.json"), encoding="utf-8") as f:
            current = json.load(f)["globals"]["current project"]
        self.assertNotEqual(os.path.normcase(current), os.path.normcase(TEST_PROJECT))


if __name__ == "__main__":
    unittest.main()
