import json
import os
import shutil
import socket
import tempfile
import unittest

from fakes import FakeLineServer, send_line
from unity_bridge import endpoint, protocol
from unity_bridge.command_server import CommandServer
from unity_bridge.unity_client import UnityClient


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.project = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)

    def write_session(self, port, token, pid=1234):
        folder = os.path.join(self.project, "Library", "PrismUnity")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "session.json"), "w") as f:
            json.dump({"unityPort": port, "prismPort": 1, "token": token, "unityPid": pid}, f)

    def test_prism_endpoint_round_trip(self):
        endpoint.write_prism_endpoint(self.project, 51234, 999)
        path = os.path.join(self.project, "Library", "PrismUnity", "prism.json")
        with open(path) as f:
            self.assertEqual(json.load(f), {"port": 51234, "pid": 999})

    def test_read_unity_endpoint(self):
        self.write_session(40000, "tok")
        self.assertEqual(endpoint.read_unity_endpoint(self.project), (40000, "tok"))
        self.assertIsNone(endpoint.read_unity_endpoint(os.path.join(self.project, "missing")))

    def test_unity_client_follows_session_file(self):
        # Unity may move to another port after a domain reload; Prism must follow session.json.
        with FakeLineServer(lambda m: protocol.ok(m["id"], m["token"])) as srv:
            self.write_session(srv.port, "fresh-token")
            client = UnityClient(1, "stale-token", project=self.project)
            self.assertEqual(client.call("ping"), "fresh-token")

    def test_server_falls_back_when_port_taken(self):
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        taken = blocker.getsockname()[1]
        try:
            srv = CommandServer(taken, "t", lambda m: protocol.ok(m["id"], "ok"), lambda fn: fn())
            srv.start()
            try:
                self.assertNotEqual(srv.port, taken)
                self.assertTrue(send_line(srv.port, protocol.make_request("ping", None, "t", False))["ok"])
            finally:
                srv.stop()
        finally:
            blocker.close()


if __name__ == "__main__":
    unittest.main()
