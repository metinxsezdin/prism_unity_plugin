import os
import shutil
import unittest
import uuid

from mcp_server import it_support
from mcp_server.fake_core import call


@unittest.skipUnless(it_support.RUN, it_support.SKIP_REASON)
class CreateIntegrationTests(unittest.TestCase):
    def setUp(self):
        import prism_mcp.tools_create  # noqa: F401
        import prism_mcp.tools_query  # noqa: F401

        self.session = it_support.session()
        self.tag = uuid.uuid4().hex[:6]
        self.made = []

    def tearDown(self):
        core = self.session.core
        for entity in self.made:
            shutil.rmtree(core.getEntityPath(entity=entity), ignore_errors=True)
        seq = os.path.join(core.projectPath, "03_Production", "Shots", "sq_mcp")
        if os.path.isdir(seq) and not os.listdir(seq):
            os.rmdir(seq)

    def _ok(self, tool, **args):
        r = call(self.session, tool, **args)
        self.assertTrue(r["ok"], r)
        return r["result"]

    def test_real_create_asset_department_task(self):
        asset = {"type": "asset", "asset_path": "Props/McpTest_%s" % self.tag}
        self.made.append(asset)
        self.assertTrue(self._ok("create_entity", entity=asset, description="made by the MCP tests")["created"])
        self.assertFalse(self._ok("create_entity", entity=asset)["created"])
        dep = self._ok("create_department", entity=asset, department="Modeling", defaultTasks=False)
        self.assertTrue(dep["created"])
        self.assertTrue(self._ok("create_task", entity=asset, department="Modeling", task="Sculpt")["created"])
        info = self._ok("get_entity", entity=asset)
        self.assertEqual(info["description"], "made by the MCP tests")
        self.assertIn({"name": dep["department"], "tasks": ["Sculpt"]}, info["departments"])

    def test_real_create_shot_with_range(self):
        shot = {"type": "shot", "sequence": "sq_mcp", "shot": "sh_%s" % self.tag}
        self.made.append(shot)
        self.assertTrue(self._ok("create_entity", entity=shot, frameRange=[1001, 1048])["created"])
        self.assertEqual(self._ok("get_entity", entity=shot)["frameRange"], [1001, 1048])


if __name__ == "__main__":
    unittest.main()
