"""Regression tests for the minor findings of the final review."""

import os
import shutil
import socket
import tempfile
import threading
import time
import unittest

from fakes import FakeCore, FakeLineServer, send_line
from unity_bridge import protocol
from unity_bridge.command_server import MAX_LINE_BYTES, CommandServer
from unity_bridge.headless import headless
from unity_bridge.projects import pin_project
from unity_bridge.protocol import BridgeError
from unity_bridge.unity_client import UnityClient


def run_inline(fn):
    return fn()


class ExpiredJobTests(unittest.TestCase):
    def test_job_that_waited_past_its_deadline_is_not_run(self):
        ran = []

        def slow_main_thread(fn):
            time.sleep(0.4)  # Prism's main thread was busy
            return fn()

        def handle(msg):
            ran.append(msg["cmd"])
            return protocol.ok(msg["id"], True)

        srv = CommandServer(0, "t", handle, slow_main_thread)
        srv.start()
        try:
            resp = send_line(srv.port, protocol.make_request("saveVersion", {"_timeoutSec": 0.1}, "t", False))
            self.assertEqual(resp["error"]["code"], "timeout")
            self.assertEqual(ran, [], "a request the caller gave up on must not run later")
        finally:
            srv.stop()

    def test_job_within_deadline_runs(self):
        srv = CommandServer(0, "t", lambda m: protocol.ok(m["id"], "done"), run_inline)
        srv.start()
        try:
            resp = send_line(srv.port, protocol.make_request("ping", {"_timeoutSec": 5}, "t", False))
            self.assertEqual(resp["result"], "done")
        finally:
            srv.stop()


class RobustServerTests(unittest.TestCase):
    def setUp(self):
        self.srv = CommandServer(0, "secret", lambda m: protocol.ok(m["id"], "pong"), run_inline)
        self.srv.start()

    def tearDown(self):
        self.srv.stop()

    def test_non_ascii_token_is_bad_token_not_a_crash(self):
        resp = send_line(self.srv.port, protocol.make_request("ping", None, "çay", False))
        self.assertEqual(resp["error"]["code"], "bad_token")
        self.assertTrue(send_line(self.srv.port, protocol.make_request("ping", None, "secret", False))["ok"])

    def test_oversized_line_is_rejected(self):
        with socket.create_connection(("127.0.0.1", self.srv.port), timeout=5) as s:
            s.sendall(b"x" * (MAX_LINE_BYTES + 10) + b"\n")
            data = s.recv(65536)
        self.assertEqual(protocol.decode(data)["error"]["code"], "bad_request")
        self.assertTrue(send_line(self.srv.port, protocol.make_request("ping", None, "secret", False))["ok"])


class HeadlessPopupTests(unittest.TestCase):
    def test_error_notice_is_internal_not_needs_input(self):
        core = FakeCore()
        with self.assertRaises(BridgeError) as ctx:
            with headless(core):
                core.popup("Could not create this folder", severity="warning")
        self.assertEqual(ctx.exception.code, "internal")
        self.assertIn("Could not create this folder", ctx.exception.message)

    def test_question_is_needs_input(self):
        core = FakeCore()
        with self.assertRaises(BridgeError) as ctx:
            with headless(core):
                core.popupQuestion("Overwrite?")
        self.assertEqual(ctx.exception.code, "needs_input")

    def test_missing_user_does_not_open_prism_user_dialog(self):
        class Users:
            def ensureUser(self):
                raise AssertionError("the Prism user dialog would open")

        core = FakeCore()
        core.users = Users()
        core.user = ""
        with self.assertRaises(BridgeError) as ctx:
            with headless(core):
                core.users.ensureUser()
        self.assertEqual(ctx.exception.code, "needs_input")

    def test_existing_user_passes(self):
        class Users:
            def ensureUser(self):
                return True

        core = FakeCore()
        core.users = Users()
        core.user = "adm"
        with headless(core):
            self.assertTrue(core.users.ensureUser())


class ReloadRetryTests(unittest.TestCase):
    def test_unity_that_stays_away_is_unity_busy(self):
        with FakeLineServer(lambda m: None) as srv:
            port = srv.port
        start = time.monotonic()
        with self.assertRaises(BridgeError) as ctx:
            UnityClient(port, "tok", timeout=1.0, reload_wait=1.0).call("ping")
        self.assertEqual(ctx.exception.code, "unity_busy")
        self.assertIn("compil", ctx.exception.message)
        self.assertLess(time.monotonic() - start, 8)

    def test_unity_that_comes_back_is_reached(self):
        holder = {}
        with FakeLineServer(lambda m: None) as srv:
            port = srv.port

        def start_later():
            time.sleep(0.8)
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            s.listen(1)
            holder["sock"] = s
            conn, _ = s.accept()
            line = conn.makefile("rb").readline()
            conn.sendall(protocol.encode(protocol.ok(protocol.decode(line)["id"], "back")))
            conn.close()

        t = threading.Thread(target=start_later, daemon=True)
        t.start()
        try:
            self.assertEqual(UnityClient(port, "tok", timeout=2.0, reload_wait=10.0).call("ping"), "back")
        finally:
            t.join(5)
            if "sock" in holder:
                holder["sock"].close()


class LauncherProjectCheckTests(unittest.TestCase):
    def test_missing_project_config_is_reported(self):
        from Prism_Unity_Launcher import check_prism_project

        self.assertIsNone(check_prism_project(""))
        self.assertIn("M:/gone/00_Pipeline/pipeline.json", check_prism_project("M:/gone/00_Pipeline/pipeline.json"))
        tmp = tempfile.mkdtemp()
        try:
            cfg = os.path.join(tmp, "pipeline.json")
            open(cfg, "w").close()
            self.assertIsNone(check_prism_project(cfg))
        finally:
            shutil.rmtree(tmp)


class PinProjectLockTests(unittest.TestCase):
    def test_concurrent_pins_do_not_interleave(self):
        events = []

        class Core:
            prismIni = ""

            def __init__(self):
                self.config = {"current project": "M:/user"}

            def getConfig(self, cat, param, **kw):
                return shared["current"]

            def setConfig(self, cat, param, val, **kw):
                shared["current"] = val

            def changeProject(self, path, writeToConfig=None):
                events.append(("in", path))
                shared["current"] = path
                time.sleep(0.2)
                events.append(("out", path))

        shared = {"current": "M:/user"}
        threads = [threading.Thread(target=pin_project, args=(Core(), "P%d" % i)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual([e[0] for e in events], ["in", "out", "in", "out"], events)
        self.assertEqual(shared["current"], "M:/user")


if __name__ == "__main__":
    unittest.main()
