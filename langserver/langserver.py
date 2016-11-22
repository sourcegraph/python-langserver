import sys
import jedi
import argparse
import socket
import socketserver
from abc import ABC, abstractmethod

from langserver.fs import LocalFileSystem, RemoteFileSystem
from langserver.jsonrpc import JSONRPC2Server, ReadWriter, TCPReadWriter
from langserver.log import log

# TODO(renfred) non-global config.



class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

class LangserverTCPTransport(socketserver.StreamRequestHandler):
    def handle(self):
        s = LangServer(conn=TCPReadWriter(self.rfile, self.wfile))
        s.serve()

class LangServer(JSONRPC2Server):
    # TODO figure out how to set self.fs instead of using this method.
    def get_fs(self):
        if remote_fs:
            return RemoteFileSystem(self)
        else:
            return LocalFileSystem()

    def handle(self, id, request):
        log("REQUEST: ", request)
        resp = None

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
        elif request["method"] == "workspace/symbol":
            resp = []

        if resp is not None:
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
        ThreadingTCPServer.allow_reuse_address = True
        s = ThreadingTCPServer((host, addr), LangserverTCPTransport)
        try:
            s.serve_forever()
        finally:
            s.shutdown()

if __name__ == "__main__":
    main()
