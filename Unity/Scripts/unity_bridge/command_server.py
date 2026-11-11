"""Unity → Prism listener: accepts tokened requests on 127.0.0.1 only."""

import hmac
import socket
import threading
import time
import traceback

from . import protocol
from .protocol import BridgeError

HOST = "127.0.0.1"
MAX_LINE_BYTES = 4 * 1024 * 1024  # one request; anything longer is not ours
IDLE_TIMEOUT_SEC = 300


class CommandServer(object):
    """Line-based JSON server.

    handle(msg) -> response dict does the work; run_on_main(fn) -> fn() runs it on
    the thread that owns Prism's Qt objects (the launcher passes a Qt-queued invoker).
    """

    def __init__(self, port, token, handle, run_on_main):
        self.token = token
        self.handle = handle
        self.run_on_main = run_on_main
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._sock.bind((HOST, int(port)))
        except OSError:
            self._sock.bind((HOST, 0))  # taken: use any free port; the launcher publishes the real one
        self._sock.listen(8)
        self.address = self._sock.getsockname()
        self.port = self.address[1]
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, name="PrismUnityServer", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stopping.set()
        try:
            self._sock.close()
        except OSError:
            pass

    def _accept_loop(self):
        while not self._stopping.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        with conn:
            conn.settimeout(IDLE_TIMEOUT_SEC)
            reader = conn.makefile("rb")
            while True:
                try:
                    line = reader.readline(MAX_LINE_BYTES + 1)
                except (OSError, ValueError):
                    return
                if not line:
                    return
                if len(line) > MAX_LINE_BYTES and not line.endswith(b"\n"):
                    conn.sendall(protocol.encode(protocol.err(None, "bad_request", "Request is too long.")))
                    return
                if not line.strip():
                    continue
                conn.sendall(protocol.encode(self._respond(line)))

    def _respond(self, line):
        try:
            msg = protocol.decode(line)
        except BridgeError as e:
            return e.to_response(None)
        request_id = msg.get("id")
        token = msg.get("token")
        if not isinstance(token, str) or not hmac.compare_digest(token.encode("utf-8"), self.token.encode("utf-8")):
            return protocol.err(request_id, "bad_token", "Invalid session token.")
        args = msg.get("args") if isinstance(msg.get("args"), dict) else {}
        try:
            limit = float(args.get("_timeoutSec")) if args.get("_timeoutSec") is not None else None
        except (TypeError, ValueError):
            limit = None
        deadline = time.monotonic() + limit if limit else None

        def job():
            # The caller stops waiting at its deadline; a request still queued by then must not run.
            if deadline is not None and time.monotonic() > deadline:
                raise BridgeError("timeout", "The request waited too long for Prism and was dropped.")
            return self.handle(msg)

        try:
            return self.run_on_main(job)
        except BridgeError as e:
            return e.to_response(request_id)
        except Exception as e:
            traceback.print_exc()
            return protocol.err(request_id, "internal", "%s: %s" % (type(e).__name__, e))
