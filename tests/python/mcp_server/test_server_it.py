import json
import os
import subprocess
import tempfile
import unittest

import prism_env

from mcp_server import it_support

REPO = os.environ.get("PRISM_UNITY_REPO", "")
PYTHON = os.path.join(prism_env.PRISM_ROOT, "Python313", "python.exe")
SERVER = os.path.join(REPO, "PrismMcp", "server.py")


def _env():
    env = dict(os.environ)
    env["PRISM_MCP_AUDIT_LOG"] = os.path.join(tempfile.mkdtemp(), "audit.log")
    return env


def _session(*requests):
    """Run the server over stdio with these JSON-RPC requests; returns (stdout lines, stderr)."""
    lines = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in requests).encode("utf-8")
    proc = subprocess.run([PYTHON, SERVER], input=lines, capture_output=True, timeout=300, env=_env())
    return proc.stdout.decode("utf-8").splitlines(), proc.stderr.decode("utf-8", "replace")


def _call(rid, name, args):
    return {"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": {"name": name, "arguments": args}}


@unittest.skipUnless(it_support.RUN, it_support.SKIP_REASON)
class ServerIntegrationTests(unittest.TestCase):
    def test_subprocess_handshake(self):
        out, err = _session(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                                        "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            _call(3, "status", {}),
        )
        messages = [json.loads(line) for line in out]  # every stdout line is JSON-RPC
        self.assertEqual([m["id"] for m in messages], [1, 2, 3], err)
        self.assertEqual(len(messages[1]["result"]["tools"]), 27)
        status = json.loads(messages[2]["result"]["content"][0]["text"])
        self.assertTrue(status["ok"], status)
        self.assertEqual(status["result"]["prismVersion"], "v2.1.2.1")

    def test_subprocess_turkish_entity(self):
        out, err = _session(
            _call(1, "set_project", {"configPath": it_support.TEST_PROJECT}),
            _call(2, "list_versions", {"entity": {"type": "asset", "asset_path": "Props/Çay Bardağı"}, "product": "cay_model"}),
        )
        answers = [json.loads(json.loads(line)["result"]["content"][0]["text"]) for line in out]
        self.assertTrue(answers[0]["ok"], answers[0])
        self.assertEqual([v["version"] for v in answers[1]["result"]["items"] if v["version"] != "master"], ["v0001"], err)

    def test_check_exit_code_zero(self):
        proc = subprocess.run([PYTHON, SERVER, "--check"], capture_output=True, timeout=300, env=_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.decode("utf-8").startswith("Prism MCP OK: Prism v2.1.2.1"), proc.stdout)


if __name__ == "__main__":
    unittest.main()
