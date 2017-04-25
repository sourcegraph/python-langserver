import base64
import json
import random
import uuid
from collections import OrderedDict

from .log import log


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
        self.running = True
        self._msg_buffer = OrderedDict()

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
        log("RECV: ", body)
        obj = json.loads(body)
        # If the next message doesn't have an id, just give it a random key.
        self._msg_buffer[obj.get("id") or uuid.uuid4()] = obj

    def read_message(self, id=None):
        """Read a JSON RPC message sent over the current connection. If
        id is None, the next available message is returned."""
        if id is not None:
            while self._msg_buffer.get(id) is None:
                self._receive()
            return self._msg_buffer.pop(id)
        else:
            while len(self._msg_buffer) == 0:
                self._receive()
            _, msg = self._msg_buffer.popitem(last=False)
            return msg

    def _send(self, body):
        body = json.dumps(body, separators=(",", ":"))
        content_length = len(body)
        response = (
            "Content-Length: {}\r\n"
            "Content-Type: application/vscode-jsonrpc; charset=utf8\r\n\r\n"
            "{}".format(content_length, body))
        self.conn.write(response)
        log("SEND: ", body)

    def write_response(self, id, result):
        body = {
            "jsonrpc": "2.0",
            "id": id,
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
        id = random.randint(0, 2**16)  # TODO(renfred) guarantee uniqueness.
        body = {
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        }
        self._send(body)
        return self.read_message(id)

    def stop(self):
        self.running = False

    def listen(self):
        while self.running:
            try:
                request = self.read_message()
            except EOFError:
                break
            self.handle(request)
