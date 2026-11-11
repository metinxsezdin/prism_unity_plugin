"""Unity → Prism listener: accepts tokened requests on 127.0.0.1 only."""

import hmac
import socket
import threading
import traceback

from . import protocol
from .protocol import BridgeError

HOST = "127.0.0.1"


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
        self._sock.bind((HOST, int(port)))
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
            reader = conn.makefile("rb")
            for line in reader:
                if not line.strip():
                    continue
                conn.sendall(protocol.encode(self._respond(line)))

    def _respond(self, line):
        try:
            msg = protocol.decode(line)
        except BridgeError as e:
            return e.to_response(None)
        request_id = msg.get("id")
        if not isinstance(msg.get("token"), str) or not hmac.compare_digest(msg["token"], self.token):
            return protocol.err(request_id, "bad_token", "Invalid session token.")
        try:
            return self.run_on_main(lambda: self.handle(msg))
        except BridgeError as e:
            return e.to_response(request_id)
        except Exception as e:
            traceback.print_exc()
            return protocol.err(request_id, "internal", "%s: %s" % (type(e).__name__, e))
