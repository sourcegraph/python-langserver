import sys
import jedi
import argparse
import socket
import socketserver
import traceback
from os import path as filepath
from abc import ABC, abstractmethod
from typing import List

from .fs import LocalFileSystem, RemoteFileSystem
from .jsonrpc import JSONRPC2Connection, ReadWriter, TCPReadWriter
from .log import log
from .symbols import SymbolEmitter

# TODO(renfred) non-global config.
remote_fs = False

class Module:
    def __init__(self, name, path, is_package=False):
        self.name = name
        self.path = path
        self.is_package = is_package

    def __repr__(self):
        return "PythonModule({}, {})".format(self.name, self.path)

class DummyFile:
    def __init__(self, contents):
        self.contents = contents

    def read(self):
        return self.contents

    def close(self):
        pass

class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

class LangserverTCPTransport(socketserver.StreamRequestHandler):
    def handle(self):
        s = LangServer(conn=TCPReadWriter(self.rfile, self.wfile))
        s.listen()

def path_from_uri(uri):
    if not uri.startswith("file://"):
        return uri
    _, path = uri.split("file://", 1)
    return path

class LangServer(JSONRPC2Connection):
    def __init__(self, conn=None):
        super().__init__(conn=conn)
        self.root_path = None
        self.symbol_cache = None
        if remote_fs:
            self.fs = RemoteFileSystem(self)
        else:
            self.fs = LocalFileSystem()

    """Return a set of all python modules found within a given path."""
    def workspace_modules(self, path) -> List[Module]:
        dir = self.fs.listdir(path)
        modules = []
        for e in dir:
            if e.is_dir:
                subpath = filepath.join(path, e.name)
                subdir = self.fs.listdir(subpath)
                if any([s.name == "__init__.py" for s in subdir]):
                    modules.append(Module(e.name, filepath.join(subpath, "__init__.py"), True))
            else:
                name, ext = filepath.splitext(e.name)
                if ext == ".py":
                    if name == "__init__":
                        name = filepath.basename(path)
                        modules.append(Module(name, filepath.join(path, e.name), True))
                    else:
                        modules.append(Module(name, filepath.join(path, e.name)))
        return modules

    def workspace_symbols(self):
        if self.symbol_cache:
            return self.symbol_cache
        symbols = []
        for root, dirs, files in self.fs.walk(self.root_path):
            for f in files:
                name, ext = filepath.splitext(f)
                if ext == ".py":
                    src = self.fs.open(f)
                    s = SymbolEmitter(src, file=f)
                    symbols += s.symbols()
        self.symbol_cache = symbols
        return symbols

    def new_script(self, *args, **kwargs):
        """Return an initialized Jedi API Script object."""
        path = kwargs.get("path")

        def find_module_remote(string, dir=None):
            """A swap-in replacement for Jedi's find module function that uses the
            remote fs to resolve module imports."""
            if type(dir) is list: # TODO(renfred): handle list input for paths.
                dir = dir[0]
            dir = dir or filepath.dirname(path)
            modules = self.workspace_modules(dir)
            for m in modules:
                if m.name == string:
                    c = self.fs.open(m.path)
                    is_package = m.is_package
                    module_file = DummyFile(c)
                    module_path = filepath.dirname(m.path) if is_package else m.path
                    return module_file, module_path, is_package
            else:
                raise ImportError('Module "{}" not found in {}', string, dir)

        def list_modules() -> List[str]:
            modules = []
            for root, _, files in self.fs.walk(self.root_path):
                for f in files:
                    name, ext = filepath.splitext(f)
                    if ext == ".py":
                        modules.append(filepath.join(root, f))
            return modules

        def load_source(path) -> str:
            return self.fs.open(path)

        if remote_fs:
            find_module_func, list_modules_func, load_source_func = \
                find_module_remote, list_modules, load_source
        else:
            find_module_func, list_modules_func, load_source_func = None, None, None
        return jedi.api.Script(*args, **kwargs, find_module=find_module_func,
                               list_modules=list_modules_func,
                               load_source=load_source_func)

    def handle(self, id, request):
        log("REQUEST: ", request)
        resp = None

        if request["method"] == "initialize":
            params = request["params"]
            self.root_path = path_from_uri(params["rootPath"])
            resp = {
                "capabilities": {
                    "hoverProvider": True,
                    "definitionProvider": True,
                    "referencesProvider": True,
                    "workspaceSymbolProvider": True
                }
            }
        elif request["method"] == "textDocument/hover":
            resp = self.serve_hover(request)
        elif request["method"] == "textDocument/definition":
            resp = self.serve_definition(request)
        elif request["method"] == "textDocument/references":
            resp = self.serve_references(request)
        elif request["method"] == "workspace/symbol":
            resp = self.serve_symbols(request)

        if resp is not None:
            self.write_response(request["id"], resp)

    def serve_hover(self, request):
        params = request["params"]
        pos = params["position"]
        path = path_from_uri(params["textDocument"]["uri"])
        source = self.fs.open(path)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(path=path, source=source, line=pos["line"]+1,
                                 column=pos["character"])

        defs, error = [], None
        try:
            defs = script.goto_definitions()
        except Exception as e:
            # TODO return these errors using JSONRPC properly. Doing it this way
            # initially for debugging purposes.
            log(traceback.format_exc())
            error = "ERROR {}: {}".format(type(e), e)
        d = defs[0] if len(defs) > 0 else None

        # TODO(renfred): better failure mode
        if d is None:
            value = error or "Definition Not Found"
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
        path = path_from_uri(params["textDocument"]["uri"])
        source = self.fs.open(path)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(path=path, source=source, line=pos["line"]+1,
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
        path = path_from_uri(params["textDocument"]["uri"])
        source = self.fs.open(path)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(path=path, source=source, line=pos["line"]+1,
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
                        "character": u.column+len(u.name),
                    }
                }
            })
        return refs

    def serve_symbols(self, request):
        params = request["params"]

        symbols = self.workspace_symbols()
        q, limit = params.get("query"), params.get("limit")
        if q:
            symbols.sort(reverse=True, key=lambda s: s.score(q))
        if limit and len(symbols) > limit:
            symbols = symbols[:limit]

        return [{
            "name": s.name,
            "kind": s.kind.value,
            "containerName": s.container,
            "location": {
                "uri": "file://" + s.file,
                "range": {
                    "start": {
                        "line": s.line-1,
                        "character": s.col,
                    },
                    "end": {
                        "line": s.line-1,
                        "character": s.col,
                    }
                }
            },
        } for s in symbols]

def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--mode", default="stdio", help="communication (stdio|tcp)")
    # TODO use this
    parser.add_argument("--fs", default="remote", help="file system (local|remote)")
    parser.add_argument("--addr", default=4389, help="server listen (tcp)", type=int)
    parser.add_argument("--remote", default=0, help="temp, enable remote fs",
                        type=int) # TODO(renfred) remove

    args = parser.parse_args()
    rw = None

    global remote_fs
    remote_fs = bool(args.remote)

    if args.mode == "stdio":
        log("Reading on stdin, writing on stdout")
        s = LangServer(conn=ReadWriter(sys.stdin, sys.stdout))
        s.listen()
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
