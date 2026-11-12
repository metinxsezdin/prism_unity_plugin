import unittest

from mcp_server import it_support
from mcp_server.fake_core import call

LOTUS = {"type": "asset", "asset_path": "Props/Lotus"}


@unittest.skipUnless(it_support.RUN, it_support.SKIP_REASON)
class VersionsIntegrationTests(unittest.TestCase):
    def setUp(self):
        import prism_mcp.tools_query  # noqa: F401
        import prism_mcp.tools_versions  # noqa: F401

        self.session = it_support.session()
        self.before = self._master()

    def tearDown(self):
        current = self._master()
        if current == self.before:
            return
        if self.before is None:
            e = call(self.session, "delete_master", entity=LOTUS, product="lotus_model")["error"]
            call(self.session, "delete_master", entity=LOTUS, product="lotus_model", confirm=e["details"]["confirmToken"])
        else:
            e = call(self.session, "set_master", entity=LOTUS, product="lotus_model", version=self.before)["error"]
            call(self.session, "set_master", entity=LOTUS, product="lotus_model", version=self.before, confirm=e["details"]["confirmToken"])
        self.assertEqual(self._master(), self.before)

    def _master(self):
        items = call(self.session, "list_versions", entity=LOTUS, product="lotus_model")["result"]["items"]
        return next((i["contentVersion"] for i in items if i["version"] == "master"), None)

    def test_real_set_master_round_trip(self):
        target = "v0001" if self.before != "v0001" else "v0002"
        r = call(self.session, "set_master", entity=LOTUS, product="lotus_model", version=target)
        self.assertEqual(r["error"]["code"], "needs_confirmation", r)
        r = call(self.session, "set_master", entity=LOTUS, product="lotus_model", version=target, confirm=r["error"]["details"]["confirmToken"])
        self.assertTrue(r["ok"], r)
        self.assertEqual(self._master(), target)


if __name__ == "__main__":
    unittest.main()
