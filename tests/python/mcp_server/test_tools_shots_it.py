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

    def test_real_deleted_shot_leaves_no_range_or_metadata_behind(self):
        # M9 against real Prism: its shotinfo config must not keep the deleted shot's range and metadata.
        core = self.session.core
        shot = {"type": "shot", "sequence": "sq_mcp", "shot": "sh_%s" % self.tag}
        self.cleanup.append(core.getEntityPath(entity=shot))
        self.assertTrue(call(self.session, "create_entity", entity=shot, frameRange=[1001, 1024])["result"]["created"])
        self.assertTrue(call(self.session, "set_metadata", entity=shot, metaData={"mood": "calm"})["ok"])
        self.assertEqual(core.entities.getShotRange(shot), [1001, 1024])

        trash = self._confirmed("delete_shot", entity=shot)["trash"]
        self.cleanup.append(trash)
        core.configs.clearCache()
        self.assertIsNone(core.entities.getShotRange(shot))
        self.assertEqual(core.entities.getMetaData(shot), {})
        self.assertIn("1001", open(os.path.join(trash, "shotinfo.json"), encoding="utf-8").read())

        # A new shot with the same name starts clean.
        self.assertTrue(call(self.session, "create_entity", entity=shot)["result"]["created"])
        core.configs.clearCache()
        self.assertIsNone(core.entities.getShotRange(shot))
        self.assertEqual(core.entities.getMetaData(shot), {})


if __name__ == "__main__":
    unittest.main()
