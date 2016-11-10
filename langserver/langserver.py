import sys
import json
import jedi
import argparse
import socket
from abc import ABC, abstractmethod

def log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class JSONRPC2Error(Exception):
    pass

class ReadWriter(ABC):
    @abstractmethod
    def readline(self, size):
        pass

    @abstractmethod
    def read(self, size):
        pass

    @abstractmethod
    def write(self, size):
        pass

class StdIOReadWriter(ReadWriter):
    def readline(self, *args):
        return sys.stdin.readline(*args)

    def read(self, *args):
        return sys.stdin.read(*args)

    def write(self, out):
        sys.stdout.write(out)
        sys.stdout.flush()

class TCPReadWriter(ReadWriter):
    def __init__(self, conn):
        self.conn = conn
        self.buffer = ""

    def readline(self, size=None):
        buffering = True
        while buffering:
            if "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                line += "\n"
                if size:
                    line, self.buffer = line[:size], self.buffer + line[size:]
                return line
            else:
                next = self.conn.recv(4096)
                if not next:
                    buffering = False
                else:
                    self.buffer += next.decode("utf-8")

    def read(self, size):
        if len(self.buffer) >= size:
            out, self.buffer = self.buffer[:size], self.buffer[size:]
        recv_size = size - len(self.buffer)
        next = self.conn.recv(recv_size).decode("utf-8")
        out, self.buffer = self.buffer + next, self.buffer
        return out

    def write(self, out):
        self.conn.send(out.encode())

class JSONRPC2Server:
    def __init__(self, conn):
        self.conn = conn

    def handle(self, id, request):
        pass

    def _read_header_content_length(self, line):
        if len(line) < 2 or line[-2:] != "\r\n":
            print("LINE: ", line)
            raise JSONRPC2Error("Line endings must be \\r\\n")
        if line.startswith("Content-Length: "):
            _, value = line.split("Content-Length: ")
            value = value.strip()
            try:
                print("LENGTH VALUE: ", value)
                return int(value)
            except ValueError:
                raise JSONRPC2Error("Invalid Content-Length header: {}".format(value))

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

    def serve(self):
        while True:
            line = self.conn.readline()
            length = self._read_header_content_length(line)
            body = self.conn.read(length+2) # TODO(renfred): why the off-by-two?
            request = json.loads(body)
            self.handle(id, request)

class LangServer(JSONRPC2Server):
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
        source = open(path).read()
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
        source = open(path).read()
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
        source = open(path).read()
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
    parser.add_argument("--addr", default=4389, help="server listen (tcp)", type=int)

    args = parser.parse_args()
    rw = None
    if args.mode == "stdio":
        log("Reading on stdin, writing on stdout")
        rw = StdIOReadWriter()
        server = LangServer(conn=rw)
        server.serve()

    elif args.mode == "tcp":
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        config = ("localhost", args.addr)
        log("Accepting TCP connections on {}:{}".format(config[0], config[1]))
        s.bind(config)
        s.listen(1) # TODO(renfred): accept more connections?
        conn, addr = s.accept()

        rw = TCPReadWriter(conn)
        server = LangServer(conn=rw)
        try:
            server.serve()
        finally:
            conn.close()


if __name__ == "__main__":
    main()
