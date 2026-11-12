import io
import json
import os
import subprocess
import sys
import unittest

from unity_bridge.protocol import BridgeError


class StubCtx:
    def project_info(self):
        return {"name": "P", "path": "X"}


def _tools():
    from prism_mcp import registry

    tools = {}

    def echo(ctx, text):
        return text

    def boom(ctx):
        raise BridgeError("needs_input", "who?")

    tools["echo"] = registry.ToolSpec("echo", "Echo text.", {"type": "object", "properties": {"text": {"type": "string"}}}, echo, False)
    tools["boom"] = registry.ToolSpec("boom", "Always asks.", {"type": "object", "properties": {}}, boom, False)
    return tools


def _server():
    from prism_mcp.mcp_stdio import McpServer

    return McpServer(StubCtx(), tools=_tools())


def _call(server, name, args, rid=1):
    resp = server.handle({"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": {"name": name, "arguments": args}})
    return json.loads(resp["result"]["content"][0]["text"]), resp["result"]["isError"]


class McpStdioTests(unittest.TestCase):
    def test_initialize_echoes_supported_version(self):
        server = _server()
        r = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(r["result"]["serverInfo"]["name"], "prism")
        self.assertIn("tools", r["result"]["capabilities"])
        r = server.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")

    def test_notification_has_no_response(self):
        self.assertIsNone(_server().handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_tools_list_lists_registered_tools(self):
        r = _server().handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = r["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["boom", "echo"])
        self.assertTrue(all("inputSchema" in t and "description" in t for t in tools))

    def test_tools_call_success_envelope(self):
        body, is_error = _call(_server(), "echo", {"text": "hi"})
        self.assertEqual(body, {"ok": True, "project": {"name": "P", "path": "X"}, "result": "hi"})
        self.assertFalse(is_error)

    def test_tools_call_bridge_error_envelope(self):
        body, is_error = _call(_server(), "boom", {})
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "needs_input")
        self.assertEqual(body["error"]["message"], "who?")
        self.assertTrue(is_error)

    def test_bad_kwargs_is_bad_args(self):
        body, is_error = _call(_server(), "echo", {"nope": 1})
        self.assertEqual(body["error"]["code"], "bad_args")
        self.assertTrue(is_error)

    def test_unknown_method_and_bad_json(self):
        r = _server().handle({"jsonrpc": "2.0", "id": 7, "method": "resources/list"})
        self.assertEqual(r["error"]["code"], -32601)
        out = io.BytesIO()
        _server().serve(io.BytesIO(b"not json\n"), out)
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        resp = json.loads(lines[0])
        self.assertEqual(resp["error"]["code"], -32700)
        self.assertIsNone(resp["id"])

    def test_utf8_round_trip(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "echo", "arguments": {"text": "Props/Çay Bardağı"}}}
        out = io.BytesIO()
        _server().serve(io.BytesIO((json.dumps(req) + "\n").encode("utf-8")), out)
        raw = out.getvalue()
        self.assertIn("Çay Bardağı", raw.decode("utf-8"))
        self.assertEqual(json.loads(json.loads(raw)["result"]["content"][0]["text"])["result"], "Props/Çay Bardağı")

    def test_guard_stdout_keeps_protocol_stream_clean(self):
        repo = os.environ.get("PRISM_UNITY_REPO", "")
        paths = [os.path.join(repo, "PrismMcp"), os.path.join(repo, "Unity", "Scripts")]
        code = (
            "import os, sys; sys.path[:0] = %r\n"
            "from prism_mcp.mcp_stdio import guard_stdout\n"
            "out = guard_stdout()\n"
            "print('noise'); sys.stdout.flush()\n"
            "os.write(1, b'c-noise\\n')\n"
            "out.write(b'{\"x\":1}\\n')\n" % paths
        )
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=30)
        self.assertEqual(proc.stdout, b'{"x":1}\n', proc.stderr)
        self.assertIn(b"noise", proc.stderr)
        self.assertIn(b"c-noise", proc.stderr)


if __name__ == "__main__":
    unittest.main()
