import sys
import jedi
import argparse
import logging
import itertools
import multiprocessing
import socket
import socketserver
import traceback
from os import path as filepath
from abc import ABC, abstractmethod
from typing import List

from .fs import LocalFileSystem, RemoteFileSystem
from .jsonrpc import JSONRPC2Connection, ReadWriter, TCPReadWriter
from .symbols import extract_symbols

log = logging.getLogger(__name__)


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
        conn = JSONRPC2Connection(TCPReadWriter(self.rfile, self.wfile))
        s = LangServer(conn)
        s.run()


def path_from_uri(uri):
    if not uri.startswith("file://"):
        return uri
    _, path = uri.split("file://", 1)
    return path


class LangServer:
    def __init__(self, conn):
        self.conn = conn
        self.running = True
        self.root_path = None
        self.fs = None
        self.symbol_cache = None

    def run(self):
        while self.running:
            try:
                request = self.conn.read_message()
            except EOFError:
                break
            self.handle(request)

    """Return a set of all python modules found within a given path."""

    def workspace_modules(self, path) -> List[Module]:
        dir = self.fs.listdir(path)
        modules = []
        for e in dir:
            if e.is_dir:
                subpath = filepath.join(path, e.name)
                subdir = self.fs.listdir(subpath)
                if any([s.name == "__init__.py" for s in subdir]):
                    modules.append(
                        Module(e.name,
                               filepath.join(subpath, "__init__.py"), True))
            else:
                name, ext = filepath.splitext(e.name)
                if ext == ".py":
                    if name == "__init__":
                        name = filepath.basename(path)
                        modules.append(
                            Module(name, filepath.join(path, e.name), True))
                    else:
                        modules.append(
                            Module(name, filepath.join(path, e.name)))
        return modules

    def workspace_symbols(self):
        if self.symbol_cache:
            return self.symbol_cache
        py_paths = (path for path in self.fs.walk(self.root_path) if path.endswith(".py"))
        py_srces = self.fs.batch_open(py_paths)
        with multiprocessing.Pool() as p:
            symbols_chunks = p.imap_unordered(extract_symbols_star, py_srces, chunksize=10)
            symbols = list(itertools.chain.from_iterable(symbols_chunks))
        self.symbol_cache = symbols
        return symbols

    def new_script(self, *args, **kwargs):
        """Return an initialized Jedi API Script object."""
        path = kwargs.get("path")

        def find_module_remote(string, dir=None):
            """A swap-in replacement for Jedi's find module function that uses the
            remote fs to resolve module imports."""
            if type(dir) is list:  # TODO(renfred): handle list input for paths.
                dir = dir[0]
            dir = dir or filepath.dirname(path)
            modules = self.workspace_modules(dir)
            for m in modules:
                if m.name == string:
                    c = self.fs.open(m.path)
                    is_package = m.is_package
                    module_file = DummyFile(c)
                    module_path = filepath.dirname(
                        m.path) if is_package else m.path
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

        # TODO(keegan) It shouldn't matter if we are using a remote fs or not. Consider other ways to hook into the import system.
        if isinstance(self.fs, RemoteFileSystem):
            kwargs.update(
                find_module=find_module_remote,
                list_modules=list_modules,
                load_source=load_source, )
        return jedi.api.Script(*args, **kwargs)

    def handle(self, request):
        log.info("REQUEST %s %s", request.get("id"), request.get("method"))

        handler = {
            "initialize": self.serve_initialize,
            "textDocument/hover": self.serve_hover,
            "textDocument/definition": self.serve_definition,
            "textDocument/references": self.serve_references,
            "textDocument/documentSymbol": self.serve_documentSymbols,
            "workspace/symbol": self.serve_symbols,
            "shutdown": lambda *a: None,  # Shutdown is a noop
            "exit": self.serve_exit,
        }.get(request["method"], self.serve_default)

        # We handle notifs differently since we can't respond
        if "id" not in request:
            try:
                handler(request)
            except Exception as e:
                log.warning(
                    "error handling notification %s", request, exc_info=True)
            return

        try:
            resp = handler(request)
        except JSONRPC2Error as e:
            self.conn.write_error(
                request["id"], code=e.code, message=e.message, data=e.data)
        except Exception as e:
            log.warning("handler for %s failed", request, exc_info=True)
            self.conn.write_error(
                request["id"],
                code=-32603,
                message=str(e),
                data={
                    "traceback": traceback.format_exc(),
                })
            log.warning("error handling request %s", request, exc_info=True)
        else:
            self.conn.write_response(request["id"], resp)

    def serve_initialize(self, request):
        params = request["params"]
        self.root_path = path_from_uri(params["rootPath"])

        caps = params.get("capabilities", {})
        if caps.get("xcontentProvider") and caps.get("xfilesProvider"):
            # The client supports a remote fs
            self.fs = RemoteFileSystem(self.conn)
        else:
            self.fs = LocalFileSystem()

        return {
            "capabilities": {
                "hoverProvider": True,
                "definitionProvider": True,
                "referencesProvider": True,
                "documentSymbolProvider": True,
                "workspaceSymbolProvider": True,
            }
        }

    def serve_hover(self, request):
        params = request["params"]
        pos = params["position"]
        path = path_from_uri(params["textDocument"]["uri"])
        source = self.fs.open(path)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(
            path=path,
            source=source,
            line=pos["line"] + 1,
            column=pos["character"])

        defs, error = [], None
        try:
            defs = script.goto_definitions()
        except Exception as e:
            # TODO return these errors using JSONRPC properly. Doing it this way
            # initially for debugging purposes.
            log.error("Failed goto_definitions for %s", request, exc_info=True)
        d = defs[0] if len(defs) > 0 else None

        # TODO(renfred): better failure mode
        if d is None:
            value = error or "Definition Not Found"
            return {
                "contents": [{
                    "language": "markdown",
                    "value": value
                }],
            }

        hover_info = d.docstring() or d.description
        return {
            # TODO(renfred): convert reStructuredText docstrings to markdown.
            "contents": [{
                "language": "markdown",
                "value": hover_info
            }],
        }

    def serve_definition(self, request):
        params = request["params"]
        pos = params["position"]
        path = path_from_uri(params["textDocument"]["uri"])
        source = self.fs.open(path)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(
            path=path,
            source=source,
            line=pos["line"] + 1,
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
            # TODO(renfred) determine why d.module_path is empty.
            "uri": "file://" + (d.module_path or path),
            "range": {
                "start": {
                    "line": d.line - 1,
                    "character": d.column,
                },
                "end": {
                    "line": d.line - 1,
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
        script = self.new_script(
            path=path,
            source=source,
            line=pos["line"] + 1,
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
                        "line": u.line - 1,
                        "character": u.column,
                    },
                    "end": {
                        "line": u.line - 1,
                        "character": u.column + len(u.name),
                    }
                }
            })
        return refs

    def serve_symbols(self, request):
        params = request["params"]

        q, limit = params.get("query"), params.get("limit", 1000)
        symbols = ((sym.score(q), sym) for sym in self.workspace_symbols())
        symbols = ((score, sym) for (score, sym) in symbols if score >= 0)
        symbols = sorted(symbols, reverse=True, key=lambda x: x[0])[:limit]

        return [s.json_object() for (_, s) in symbols]

    def serve_documentSymbols(self, request):
        params = request["params"]
        path = path_from_uri(params["textDocument"]["uri"])
        source = self.fs.open(path)
        return [s.json_object() for s in extract_symbols(source, path)]

    def serve_exit(self, request):
        self.running = False

    def serve_default(self, request):
        raise JSONRPC2Error(
            code=-32601,
            message="method {} not found".format(request["method"]))


class JSONRPC2Error(Exception):
    def __init__(self, code, message, data=None):
        self.code = code
        self.message = message
        self.data = data


# This exists purely for passing into imap
def extract_symbols_star(args):
    path, src = args
    return list(extract_symbols(src, path))


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument(
        "--mode", default="stdio", help="communication (stdio|tcp)")
    parser.add_argument(
        "--addr", default=4389, help="server listen (tcp)", type=int)
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(level=(logging.DEBUG if args.debug else logging.INFO))
    if args.mode == "stdio":
        logging.info("Reading on stdin, writing on stdout")
        s = LangServer(conn=ReadWriter(sys.stdin, sys.stdout))
        s.run()
    elif args.mode == "tcp":
        host, addr = "0.0.0.0", args.addr
        logging.info("Accepting TCP connections on %s:%s", host, addr)
        ThreadingTCPServer.allow_reuse_address = True
        ThreadingTCPServer.daemon_threads = True
        s = ThreadingTCPServer((host, addr), LangserverTCPTransport)
        try:
            s.serve_forever()
        finally:
            s.shutdown()


if __name__ == "__main__":
    main()
