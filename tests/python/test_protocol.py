import json
import os
import unittest

from unity_bridge import protocol
from unity_bridge.protocol import BridgeError

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "protocol", "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


class ProtocolTests(unittest.TestCase):
    def test_roundtrip_fixtures(self):
        for name in ("request_ping.json", "response_ok.json", "response_error.json"):
            msg = load_fixture(name)
            self.assertEqual(protocol.decode(protocol.encode(msg)), msg, name)

    def test_encode_is_single_utf8_line(self):
        data = protocol.encode({"v": 1, "id": "x", "cmd": "ping", "args": {"name": "Çay Bardağı"}})
        self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(data.count(b"\n"), 1)
        self.assertIn("Çay Bardağı", data.decode("utf-8"))

    def test_decode_rejects_non_json(self):
        with self.assertRaises(BridgeError) as ctx:
            protocol.decode(b"hello\n")
        self.assertEqual(ctx.exception.code, "bad_request")

    def test_decode_rejects_missing_cmd(self):
        with self.assertRaises(BridgeError) as ctx:
            protocol.decode(b'{"v": 1, "id": "1", "token": "t", "args": {}}\n')
        self.assertEqual(ctx.exception.code, "bad_request")

    def test_decode_rejects_wrong_version(self):
        with self.assertRaises(BridgeError) as ctx:
            protocol.decode(b'{"v": 2, "id": "1", "cmd": "ping"}\n')
        self.assertEqual(ctx.exception.code, "bad_request")

    def test_err_has_known_code(self):
        with self.assertRaises(ValueError):
            protocol.err("1", "nope", "x")

    def test_make_request_shape(self):
        req = protocol.make_request("ping", None, "tok", interactive=True)
        self.assertEqual(req["v"], 1)
        self.assertEqual(req["cmd"], "ping")
        self.assertEqual(req["args"], {})
        self.assertEqual(req["token"], "tok")
        self.assertTrue(req["interactive"])
        self.assertTrue(req["id"])

    def test_ok_and_err_shapes(self):
        self.assertEqual(protocol.ok("1", {"a": 1}), {"v": 1, "id": "1", "ok": True, "result": {"a": 1}})
        e = protocol.err("2", "needs_input", "m", {"missing": ["task"]})
        self.assertEqual(e["error"], {"code": "needs_input", "message": "m", "details": {"missing": ["task"]}})
        self.assertFalse(e["ok"])

    def test_error_codes_match_spec(self):
        self.assertEqual(protocol.ERROR_CODES, frozenset({
            "unknown_command", "bad_token", "bad_request", "bad_args", "needs_input",
            "needs_confirmation", "prism_unavailable", "unity_busy", "missing_package",
            "source_unavailable", "timeout", "internal"}))


if __name__ == "__main__":
    unittest.main()
