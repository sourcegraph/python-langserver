import base64
import sys
import json
import jedi
import argparse
import random
import socket
import socketserver
from abc import ABC, abstractmethod

def log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class JSONRPC2Error(Exception):
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

class FileException(Exception):
    pass

class FileSystem(ABC):
    @abstractmethod
    def open(path):
        pass

class LocalFileSystem(FileSystem):
    def open(self, path):
        return open(path).read()

class RemoteFileSystem(FileSystem):
    def __init__(self, server):
        self.server = server

    def open(self, path):
        resp = self.server.send_request("fs/readFile", path)
        if resp.get("error") is not None:
            raise FileException(resp["error"])
        return base64.b64decode(resp["result"]).decode("utf-8")

class LangserverTCPTransport(socketserver.StreamRequestHandler):
    def handle(self):
        s = LangServer(conn=TCPReadWriter(self.rfile, self.wfile))
        s.serve()

class JSONRPC2Server:
    def __init__(self, conn=None):
        self.conn = conn

    def handle(self, id, request):
        pass

    def _read_header_content_length(self, line):
        if len(line) < 2 or line[-2:] != "\r\n":
            raise JSONRPC2Error("Line endings must be \\r\\n")
        if line.startswith("Content-Length: "):
            _, value = line.split("Content-Length: ")
            value = value.strip()
            try:
                return int(value)
            except ValueError:
                raise JSONRPC2Error("Invalid Content-Length header: {}".format(value))

    """Read the next JSON RPC message sent over the current connection."""
    def read_message(self):
        line = self.conn.readline()
        length = self._read_header_content_length(line)
        # Keep reading headers until we find the sentinel line for the JSON request.
        while line != "\r\n":
            line = self.conn.readline()
        body = self.conn.read(length)
        return json.loads(body)

    def write_response(self, id, result):
        body = {
            "jsonrpc": "2.0",
            "id": id,
            "result": result,
        }
        body = json.dumps(body, separators=(",", ":"))
        content_length = len(body)
        response = (
            "Content-Length: {}\r\n"
            "Content-Type: application/vscode-jsonrpc; charset=utf8\r\n\r\n"
            "{}".format(content_length, body))
        self.conn.write(response)
        log("RESPONSE: ", id, response)

    def send_request(self, method: str, params):
        body = {
            "jsonrpc": "2.0",
            "id": random.randint(0, 2**16),
            "method": method,
            "params": params,
        }
        body = json.dumps(body, separators=(",", ":"))
        content_length = len(body)
        request = (
            "Content-Length: {}\r\n"
            "Content-Type: application/vscode-jsonrpc; charset=utf8\r\n\r\n"
            "{}".format(content_length, body))
        log("SENDING REQUEST: ", request)
        self.conn.write(request)
        return self.read_message()

    def serve(self):
        while True:
            request = self.read_message()
            self.handle(id, request)

class LangServer(JSONRPC2Server):
    # TODO figure out how to set self.fs instead of using this method.
    def get_fs(self):
        # return LocalFileSystem() TODO switch to local fs via CLI flag
        return RemoteFileSystem(self)

    def handle(self, id, request):
        log("REQUEST: ", id, request)
        resp = ""

        if request["method"] == "initialize":
            resp = {
                "capabilities": {
                    # "textDocumentSync": 1,
                    "hoverProvider": True,
                    "definitionProvider": True,
                    "referencesProvider": True,
                    # "workspaceSymbolProvider": True TODO
                }
            }
        elif request["method"] == "textDocument/hover":
            resp = self.serve_hover(request)
        elif request["method"] == "textDocument/definition":
            resp = self.serve_definition(request)
        elif request["method"] == "textDocument/references":
            resp = self.serve_references(request)

        if resp:
            self.write_response(request["id"], resp)

    def path_from_uri(self, uri):
        _, path = uri.split("file://", 1)
        return path

    def serve_hover(self, request):
        params = request["params"]
        pos = params["position"]
        path = self.path_from_uri(params["textDocument"]["uri"])
        source = self.get_fs().open(path)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = jedi.api.Script(path=path, source=source, line=pos["line"]+1,
                                 column=pos["character"])

        defs, error = [], None
        try:
            defs = script.goto_definitions()
        except Exception as e:
            # TODO return these errors using JSONRPC properly. Doing it this way
            # initially for debugging purposes.
            error = "ERROR {}: {}".format(type(e), e)
        d = defs[0] if len(defs) > 0 else None

        # TODO(renfred): better failure mode
        if d is None:
            value = error or "404 Not Found"
            return {
                "contents": [{"language": "markdown", "value": value}],
            }

        hover_info = d.docstring() or d.description
        return {
            # TODO(renfred): convert reStructuredText docstrings to markdown.
            "contents": [{"language": "markdown", "value": hover_info}],
        }

    def serve_definition(self, request):
        params = request["params"]
        pos = params["position"]
        path = self.path_from_uri(params["textDocument"]["uri"])
        source = self.get_fs().open(path)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = jedi.api.Script(path=path, source=source, line=pos["line"]+1,
                                 column=pos["character"])

        defs = script.goto_definitions()
        assigns = script.goto_assignments()
        d = None
        if len(defs) > 0:
            d = defs[0]
        elif len(assigns) > 0:
            # TODO(renfred): figure out if this works in all cases.
            d = assigns[0]
        if d is None: return {}

        return {
            "uri": "file://" + d.module_path,
            "range": {
                "start": {
                    "line": d.line-1,
                    "character": d.column,
                },
                "end": {
                    "line": d.line-1,
                    "character": d.column,
                }
            }
        }

    def serve_references(self, request):
        params = request["params"]
        pos = params["position"]
        path = self.path_from_uri(params["textDocument"]["uri"])
        source = self.get_fs().open(path)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = jedi.api.Script(path=path, source=source, line=pos["line"]+1,
                                 column=pos["character"])

        usages = script.usages()
        if len(usages) == 0:
            return {}

        refs = []
        for u in usages:
            if u.is_definition():
                continue
            refs.append({
                "uri": "file://" + u.module_path,
                "range": {
                    "start": {
                        "line": u.line-1,
                        "character": u.column,
                    },
                    "end": {
                        "line": u.line-1,
                        "character": u.column,
                    }
                }
            })
        return refs

def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--mode", default="stdio", help="communication (stdio|tcp)")
    # TODO use this
    parser.add_argument("--fs", default="remote", help="file system (local|remote)")
    parser.add_argument("--addr", default=4389, help="server listen (tcp)", type=int)

    args = parser.parse_args()
    rw = None

    if args.mode == "stdio":
        log("Reading on stdin, writing on stdout")
        s = LangServer(conn=ReadWriter(sys.stdin, sys.stdout))
        s.serve()
    elif args.mode == "tcp":
        host, addr = "0.0.0.0", args.addr
        log("Accepting TCP connections on {}:{}".format(host, addr))
        socketserver.TCPServer.allow_reuse_address = True
        s = socketserver.TCPServer((host, addr), LangserverTCPTransport)
        try:
            s.serve_forever()
        finally:
            s.shutdown()

if __name__ == "__main__":
    main()
