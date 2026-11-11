import time
import unittest

from fakes import FakeLineServer
from unity_bridge import protocol
from unity_bridge.protocol import BridgeError
from unity_bridge.unity_client import UnityClient


class UnityClientTests(unittest.TestCase):
    def test_call_returns_result(self):
        with FakeLineServer(lambda m: protocol.ok(m["id"], {"fps": 30})) as srv:
            client = UnityClient(srv.port, "tok")
            self.assertEqual(client.call("getFPS"), {"fps": 30})
            sent = srv.received[0]
            self.assertEqual(sent["cmd"], "getFPS")
            self.assertEqual(sent["token"], "tok")
            self.assertFalse(sent["interactive"])

    def test_call_passes_args_and_interactive(self):
        with FakeLineServer(lambda m: protocol.ok(m["id"], None)) as srv:
            UnityClient(srv.port, "tok").call("setFPS", {"fps": 24}, interactive=True)
            self.assertEqual(srv.received[0]["args"], {"fps": 24})
            self.assertTrue(srv.received[0]["interactive"])

    def test_call_raises_bridge_error_with_code(self):
        def responder(m):
            return protocol.err(m["id"], "needs_confirmation", "Breaking update", {"removedNodes": ["Lotus/Stem"]})

        with FakeLineServer(responder) as srv:
            with self.assertRaises(BridgeError) as ctx:
                UnityClient(srv.port, "tok").call("updateProduct")
            self.assertEqual(ctx.exception.code, "needs_confirmation")
            self.assertEqual(ctx.exception.details, {"removedNodes": ["Lotus/Stem"]})

    def test_call_times_out(self):
        with FakeLineServer(lambda m: None) as srv:
            start = time.monotonic()
            with self.assertRaises(BridgeError) as ctx:
                UnityClient(srv.port, "tok").call("playblast", timeout=0.5)
            self.assertEqual(ctx.exception.code, "timeout")
            self.assertLess(time.monotonic() - start, 2.0)

    def test_call_unreachable_unity(self):
        with FakeLineServer(lambda m: None) as srv:
            port = srv.port
        with self.assertRaises(BridgeError) as ctx:
            UnityClient(port, "tok", timeout=1.0).call("ping")
        self.assertEqual(ctx.exception.code, "internal")
        self.assertIn("Unity", ctx.exception.message)

    def test_two_clients_two_servers_no_crosstalk(self):
        with FakeLineServer(lambda m: protocol.ok(m["id"], "A")) as a, \
                FakeLineServer(lambda m: protocol.ok(m["id"], "B")) as b:
            ca, cb = UnityClient(a.port, "ta"), UnityClient(b.port, "tb")
            for _ in range(5):
                self.assertEqual(ca.call("ping"), "A")
                self.assertEqual(cb.call("ping"), "B")
            self.assertTrue(all(m["token"] == "ta" for m in a.received))
            self.assertTrue(all(m["token"] == "tb" for m in b.received))


if __name__ == "__main__":
    unittest.main()
