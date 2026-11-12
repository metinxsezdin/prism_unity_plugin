import os
import shutil
import unittest
import uuid

from mcp_server import it_support
from mcp_server.fake_core import call


@unittest.skipUnless(it_support.RUN, it_support.SKIP_REASON)
class ShotsIntegrationTests(unittest.TestCase):
    def setUp(self):
        import prism_mcp.tools_create  # noqa: F401
        import prism_mcp.tools_shots  # noqa: F401

        self.session = it_support.session()
        self.tag = uuid.uuid4().hex[:6]
        self.cleanup = []

    def tearDown(self):
        for path in self.cleanup:
            shutil.rmtree(path, ignore_errors=True)
        seq = os.path.join(self.session.core.projectPath, "03_Production", "Shots", "sq_mcp")
        if os.path.isdir(seq) and not os.listdir(seq):
            os.rmdir(seq)
        trash = os.path.join(self.session.core.projectPath, "00_Pipeline", "Trash")
        if os.path.isdir(trash) and not os.listdir(trash):
            os.rmdir(trash)

    def _confirmed(self, tool, **args):
        r = call(self.session, tool, **args)
        self.assertEqual(r["error"]["code"], "needs_confirmation", r)
        r = call(self.session, tool, confirm=r["error"]["details"]["confirmToken"], **args)
        self.assertTrue(r["ok"], r)
        return r["result"]

    def test_real_rename_then_delete_shot(self):
        core = self.session.core
        shot = {"type": "shot", "sequence": "sq_mcp", "shot": "sh_%s" % self.tag}
        renamed = dict(shot, shot="sh_%s_b" % self.tag)
        self.cleanup += [core.getEntityPath(entity=shot), core.getEntityPath(entity=renamed)]
        self.assertTrue(call(self.session, "create_entity", entity=shot)["result"]["created"])

        self.assertEqual(self._confirmed("rename", entity=shot, newName=renamed["shot"])["to"], renamed)
        self.assertFalse(os.path.exists(core.getEntityPath(entity=shot)))
        self.assertTrue(os.path.isdir(core.getEntityPath(entity=renamed)))

        trash = self._confirmed("delete_shot", entity=renamed)["trash"]
        self.cleanup.append(trash)
        self.assertFalse(os.path.exists(core.getEntityPath(entity=renamed)))
        self.assertTrue(os.path.isdir(os.path.join(trash, "global")))


if __name__ == "__main__":
    unittest.main()
