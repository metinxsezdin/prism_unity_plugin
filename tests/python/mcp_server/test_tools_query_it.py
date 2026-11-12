import unittest

from mcp_server import it_support
from mcp_server.fake_core import call


@unittest.skipUnless(it_support.RUN, it_support.SKIP_REASON)
class QueryIntegrationTests(unittest.TestCase):
    def setUp(self):
        import prism_mcp.tools_query  # noqa: F401

        self.session = it_support.session()

    def test_real_list_entities_has_test_assets(self):
        r = call(self.session, "list_entities")
        self.assertTrue(r["ok"], r)
        paths = {i["entity"]["asset_path"] for i in r["result"]["items"]}
        self.assertTrue({"Props/Lotus", "Props/Çay Bardağı", "Scenes/MeditationRoom"} <= paths, paths)

    def test_real_list_versions_lotus(self):
        r = call(self.session, "list_versions", entity={"type": "asset", "asset_path": "Props/Lotus"}, product="lotus_model")
        self.assertTrue(r["ok"], r)
        versions = [i for i in r["result"]["items"] if i["version"] != "master"]
        self.assertEqual([v["version"] for v in versions], ["v0001", "v0002", "v0003"])
        self.assertEqual(versions[1]["comment"], "bigger petals")

    def test_real_get_entity(self):
        r = call(self.session, "get_entity", entity={"type": "asset", "asset_path": "Props/Lotus"})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["result"]["entity"]["asset_path"], "Props/Lotus")


if __name__ == "__main__":
    unittest.main()
