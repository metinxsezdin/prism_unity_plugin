import unittest

from unity_bridge.protocol import BridgeError


class ConfirmTests(unittest.TestCase):
    def _require(self, args, state):
        from prism_mcp import confirm

        confirm.require(None, "set_master", args, "Lotus master: v0002 → v0003", {"from": "v0002", "to": "v0003"}, state)

    def _preview(self, args, state):
        with self.assertRaises(BridgeError) as cm:
            self._require(args, state)
        self.assertEqual(cm.exception.code, "needs_confirmation")
        return cm.exception

    def test_first_call_raises_needs_confirmation_with_token(self):
        e = self._preview({"product": "lotus_model"}, ["v0002"])
        self.assertEqual(e.message, "Lotus master: v0002 → v0003")
        self.assertEqual(e.details["summary"], "Lotus master: v0002 → v0003")
        self.assertEqual(e.details["changes"], {"from": "v0002", "to": "v0003"})
        self.assertEqual(len(e.details["confirmToken"]), 12)

    def test_matching_token_proceeds(self):
        token = self._preview({"product": "lotus_model"}, ["v0002"]).details["confirmToken"]
        self._require({"product": "lotus_model", "confirm": token}, ["v0002"])  # no exception

    def test_stale_token_is_refused(self):
        token = self._preview({"product": "lotus_model"}, ["v0002"]).details["confirmToken"]
        e = self._preview({"product": "lotus_model", "confirm": token}, ["v0003"])
        self.assertNotEqual(e.details["confirmToken"], token)

    def test_token_ignores_confirm_arg(self):
        from prism_mcp import confirm

        self.assertEqual(confirm.token("t", {"a": 1}, [1]), confirm.token("t", {"a": 1, "confirm": "x"}, [1]))
        self.assertNotEqual(confirm.token("t", {"a": 1}, [1]), confirm.token("t", {"a": 2}, [1]))


if __name__ == "__main__":
    unittest.main()
