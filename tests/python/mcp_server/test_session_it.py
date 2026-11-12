import os
import unittest

from mcp_server import it_support
from mcp_server.fake_core import call


@unittest.skipUnless(it_support.RUN, it_support.SKIP_REASON)
class SessionIntegrationTests(unittest.TestCase):
    def setUp(self):
        import prism_mcp.tools_session  # noqa: F401

        self.session = it_support.session()

    def test_real_status(self):
        r = call(self.session, "status")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["result"]["prismVersion"], "v2.1.2.1")
        self.assertTrue(r["result"]["user"])

    def test_set_project_to_test_project_leaves_global_choice(self):
        before = it_support.users_current_project()
        r = call(self.session, "set_project", configPath=it_support.TEST_PROJECT)
        self.assertTrue(r["ok"], r)
        self.assertEqual(os.path.normcase(self.session.core.prismIni), os.path.normcase(it_support.TEST_PROJECT))
        self.assertEqual(it_support.users_current_project(), before)


if __name__ == "__main__":
    unittest.main()
