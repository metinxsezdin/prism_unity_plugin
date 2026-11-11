import socket
import unittest

from fakes import send_line
from unity_bridge import protocol
from unity_bridge.command_server import CommandServer


def run_inline(fn):
    return fn()


def echo_handle(msg):
    if msg["cmd"] == "ping":
        return protocol.ok(msg["id"], "pong")
    return protocol.err(msg["id"], "unknown_command", "Unknown command: %s" % msg["cmd"])


class CommandServerTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def handle(msg):
            self.calls.append(msg["cmd"])
            return echo_handle(msg)

        self.server = CommandServer(0, "secret", handle, run_inline)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def test_valid_request_is_handled(self):
        resp = send_line(self.server.port, protocol.make_request("ping", None, "secret", False))
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["result"], "pong")

    def test_server_rejects_bad_token(self):
        resp = send_line(self.server.port, protocol.make_request("ping", None, "wrong", False))
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_token")
        self.assertEqual(self.calls, [])

    def test_server_rejects_unknown_command(self):
        resp = send_line(self.server.port, protocol.make_request("os.system", {"x": "calc"}, "secret", False))
        self.assertEqual(resp["error"]["code"], "unknown_command")

    def test_server_rejects_garbage_and_keeps_running(self):
        with socket.create_connection(("127.0.0.1", self.server.port), timeout=3) as s:
            s.sendall(b"not json\n")
            data = s.recv(65536)
        self.assertEqual(protocol.decode(data)["error"]["code"], "bad_request")
        resp = send_line(self.server.port, protocol.make_request("ping", None, "secret", False))
        self.assertTrue(resp["ok"])

    def test_handler_exception_becomes_internal_error(self):
        def boom(msg):
            raise RuntimeError("kaboom")

        srv = CommandServer(0, "secret", boom, run_inline)
        srv.start()
        try:
            resp = send_line(srv.port, protocol.make_request("ping", None, "secret", False))
            self.assertEqual(resp["error"]["code"], "internal")
            self.assertIn("kaboom", resp["error"]["message"])
        finally:
            srv.stop()

    def test_server_binds_loopback_only(self):
        self.assertEqual(self.server.address[0], "127.0.0.1")
        try:
            lan_ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            lan_ip = None
        if lan_ip and not lan_ip.startswith("127."):
            with self.assertRaises(OSError):
                socket.create_connection((lan_ip, self.server.port), timeout=1).close()


if __name__ == "__main__":
    unittest.main()
