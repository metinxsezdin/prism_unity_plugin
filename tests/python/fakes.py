"""Test doubles shared by the Python unit tests."""

import socket
import socketserver
import threading

from unity_bridge import protocol


class FakeLineServer:
    """A loopback TCP server that answers each JSON line with responder(msg).

    responder returns a response dict, or None to never answer (for timeout tests).
    """

    def __init__(self, responder):
        self.received = []
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                for line in self.rfile:
                    msg = protocol.decode(line)
                    outer.received.append(msg)
                    resp = responder(msg)
                    if resp is None:
                        threading.Event().wait(5)
                        return
                    self.wfile.write(protocol.encode(resp))
                    self.wfile.flush()

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def send_line(port, msg, timeout=3.0):
    """Send one request to a server and return the decoded response."""
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        s.sendall(protocol.encode(msg))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    return protocol.decode(buf)


class FakeCore:
    """Minimal stand-in for PrismCore: prismArgs plus popup functions that record calls."""

    def __init__(self):
        self.prismArgs = []
        self.popups = []

    def popup(self, text, title=None, severity="warning", **kwargs):
        self.popups.append(text)

    def popupQuestion(self, text, title=None, buttons=None, **kwargs):
        self.popups.append(text)
        return buttons[0] if buttons else "Yes"
