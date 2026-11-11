"""Prism → Unity calls over the loopback bridge."""

import socket

from . import protocol
from .protocol import BridgeError

HOST = "127.0.0.1"


class UnityClient(object):
    def __init__(self, port, token, timeout=10.0):
        self.port = int(port)
        self.token = token
        self.timeout = timeout

    def call(self, cmd, args=None, interactive=False, timeout=None):
        """Send one command to the Unity editor and return its result.

        Raises BridgeError with the Unity-side code on an error response,
        "timeout" when Unity does not answer in time, and "internal" when the
        editor cannot be reached at all.
        """
        timeout = self.timeout if timeout is None else timeout
        # Unity enforces its own limit from _timeoutSec (10 s by default); send ours so long
        # calls (playblast, big imports, scene saves) are not cut off on the Unity side.
        args = dict(args or {}, _timeoutSec=timeout)
        request = protocol.make_request(cmd, args, self.token, interactive)
        try:
            # Windows retries refused loopback connects for ~2 s, so a connect-phase
            # timeout means "nobody is listening", not "Unity is busy".
            sock = socket.create_connection((HOST, self.port), timeout=min(timeout, 5.0))
        except OSError as e:
            raise BridgeError("internal", "Unity editor is not reachable on port %s (%s)." % (self.port, e))
        try:
            with sock:
                sock.settimeout(timeout)
                sock.sendall(protocol.encode(request))
                data = self._read_line(sock)
        except socket.timeout:
            raise BridgeError("timeout", "Unity did not answer '%s' within %.1f s." % (cmd, timeout))
        except OSError as e:
            raise BridgeError("internal", "Connection to the Unity editor failed (%s)." % e)

        response = protocol.decode(data)
        if response.get("id") != request["id"]:
            raise BridgeError("internal", "Unity answered a different request.")
        if response.get("ok"):
            return response.get("result")
        error = response.get("error") or {}
        code = error.get("code") if error.get("code") in protocol.ERROR_CODES else "internal"
        raise BridgeError(code, error.get("message", ""), error.get("details"))

    @staticmethod
    def _read_line(sock):
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        if not buf:
            raise OSError("connection closed without a response")
        return buf
