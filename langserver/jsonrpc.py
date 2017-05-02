import base64
import json
import random
import uuid
import logging
import queue
import threading
from collections import deque

log = logging.getLogger(__name__)


class JSONRPC2ProtocolError(Exception):
    pass


class ReadWriter:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    def readline(self, *args):
        return self.reader.readline(*args)

    def read(self, *args):
        return self.reader.read(*args)

    def write(self, out):
        self.writer.write(out)
        self.writer.flush()


class TCPReadWriter(ReadWriter):
    def readline(self, *args):
        data = self.reader.readline(*args)
        return data.decode("utf-8")

    def read(self, *args):
        return self.reader.read(*args).decode("utf-8")

    def write(self, out):
        self.writer.write(out.encode())
        self.writer.flush()


class JSONRPC2Connection:
    def __init__(self, conn=None):
        self.conn = conn
        self._msg_buffer = deque()
        self._next_id = 1

    def _read_header_content_length(self, line):
        if len(line) < 2 or line[-2:] != "\r\n":
            raise JSONRPC2ProtocolError("Line endings must be \\r\\n")
        if line.startswith("Content-Length: "):
            _, value = line.split("Content-Length: ")
            value = value.strip()
            try:
                return int(value)
            except ValueError:
                raise JSONRPC2ProtocolError(
                    "Invalid Content-Length header: {}".format(value))

    def _receive(self):
        line = self.conn.readline()
        if line == "":
            raise EOFError()
        length = self._read_header_content_length(line)
        # Keep reading headers until we find the sentinel line for the JSON request.
        while line != "\r\n":
            line = self.conn.readline()
        body = self.conn.read(length)
        log.debug("RECV %s", body)
        return json.loads(body)

    def read_message(self, want=None):
        """Read a JSON RPC message sent over the current connection. If
        id is None, the next available message is returned."""
        if want is None:
            if self._msg_buffer:
                return self._msg_buffer.popleft()
            return self._receive()

        # First check if our buffer contains something we want.
        msg = deque_find_and_pop(self._msg_buffer, want)
        if msg:
            return msg

        # We need to keep receiving until we find something we want.
        # Things we don't want are put into the buffer for future callers.
        while True:
            msg = self._receive()
            if want(msg):
                return msg
            self._msg_buffer.append(msg)

    def _send(self, body):
        body = json.dumps(body, separators=(",", ":"))
        content_length = len(body)
        response = (
            "Content-Length: {}\r\n"
            "Content-Type: application/vscode-jsonrpc; charset=utf8\r\n\r\n"
            "{}".format(content_length, body))
        self.conn.write(response)
        log.debug("SEND %s", body)

    def write_response(self, rid, result):
        body = {
            "jsonrpc": "2.0",
            "id": rid,
            "result": result,
        }
        self._send(body)

    def write_error(self, rid, code, message, data=None):
        e = {
            "code": code,
            "message": message,
        }
        if data is not None:
            e["data"] = data
        body = {
            "jsonrpc": "2.0",
            "id": rid,
            "error": e,
        }
        self._send(body)

    def send_request(self, method: str, params):
        rid = self._next_id
        self._next_id += 1
        body = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": method,
            "params": params,
        }
        self._send(body)
        return self.read_message(want=lambda msg: msg.get("id") == rid)

    def send_request_batch(self, requests):
        """Pipelines requests and returns responses.

        The responses is a generator were the nth response corresponds with the
        nth request. Users must read the generator until the end, otherwise you
        will leak a thread."""

        # We communicate the request ids using a thread safe queue.
        # It also allows us to bound the number of concurrent requests.
        q = queue.Queue(100)

        def send():
            for method, params in requests:
                rid = self._next_id
                self._next_id += 1
                q.put(rid)
                body = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "method": method,
                    "params": params,
                }
                self._send(body)

            # Sentinal value to indicate we are done
            q.put(None)

        threading.Thread(target=send).start()

        while True:
            rid = q.get()
            if rid is None:
                break
            yield self.read_message(want=lambda msg: msg.get("id") == rid)


def deque_find_and_pop(d, f):
    idx = None
    for i, v in enumerate(d):
        if f(v):
            idx = i
            break
    if idx is None:
        return None
    d.rotate(-idx)
    v = d.popleft()
    d.rotate(idx)
    return v
