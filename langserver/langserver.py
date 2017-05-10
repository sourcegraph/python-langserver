import logging
import socketserver
import sys
import traceback

from .fs import LocalFileSystem, RemoteFileSystem
from .tracer import Tracer
from .jedi import RemoteJedi
from .jsonrpc import JSONRPC2Connection, ReadWriter, TCPReadWriter
from .symbols import extract_symbols, workspace_symbols

log = logging.getLogger(__name__)


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
        self.all_symbols = None

    def run(self):
        while self.running:
            try:
                request = self.conn.read_message()
            except EOFError:
                break
            self.handle(request)

    def handle(self, request):

        handler_span = Tracer.start_span(request["method"])

        log.info("REQUEST %s %s", request.get("id"), request.get("method"))

        noop = lambda *a: None
        handler = {
            "initialize": self.serve_initialize,
            "textDocument/hover": self.serve_hover,
            "textDocument/definition": self.serve_definition,
            "textDocument/references": self.serve_references,
            "textDocument/documentSymbol": self.serve_documentSymbols,
            "workspace/symbol": self.serve_symbols,
            "$/cancelRequest": noop,
            "shutdown": noop,
            "exit": self.serve_exit,
        }.get(request["method"], self.serve_default)

        # We handle notifications differently since we can't respond
        if "id" not in request:
            try:
                handler(request, handler_span)
            except Exception as e:
                log.warning(
                    "error handling notification %s", request, exc_info=True)
            return

        try:
            resp = handler(request, handler_span)
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
            write_response_span = Tracer.start_span("send_response", handler_span)
            self.conn.write_response(request["id"], resp)
            write_response_span.finish()

        handler_span.finish()

    def new_script(self, *args, **kwargs):
        return RemoteJedi(self.fs, self.root_path).new_script(*args, **kwargs)

    @staticmethod
    def goto_definitions(script, request, parent_span):
        def_span = Tracer.start_span("Script.goto_definitions", parent_span)
        try:
            return script.goto_definitions()
        except Exception as e:
            # TODO return these errors using JSONRPC properly. Doing it this way
            # initially for debugging purposes.
            log.error("Failed goto_definitions for %s", request, exc_info=True)
            return []
        finally:
            def_span.finish()

    @staticmethod
    def usages(script, parent_span):
        usages_span = Tracer.start_span("Script.usages", parent_span)
        usages = script.usages()
        usages_span.finish()
        return usages

    def serve_initialize(self, request, parent_span):
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

    def serve_hover(self, request, parent_span):
        params = request["params"]
        pos = params["position"]
        path = path_from_uri(params["textDocument"]["uri"])
        source = self.fs.open(path, parent_span)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(
            path=path,
            source=source,
            line=pos["line"] + 1,
            column=pos["character"],
            parent_span=parent_span
        )

        defs = LangServer.goto_definitions(script, request, parent_span)

        # The code from this point onwards is modifed from the MIT licensed github.com/DonJayamanne/pythonVSCode

        def generate_signature(completion):
            if completion.type in ['module'
                                   ] or not hasattr(completion, 'params'):
                return ''
            return '%s(%s)' % (completion.name,
                               ', '.join(p.description
                                         for p in completion.params if p))

        def get_definition_type(definition):
            is_built_in = definition.in_builtin_module
            try:
                if definition.type in ['statement'
                                       ] and definition.name.isupper():
                    return 'constant'
                basic_types = {
                    'module': 'import',
                    'instance': 'variable',
                    'statement': 'value',
                    'param': 'variable',
                }
                return basic_types.get(definition.type, definition.type)
            except Exception:
                return 'builtin'

        results = []
        for definition in defs:
            signature = definition.name
            description = None
            if definition.type in ('class', 'function'):
                signature = generate_signature(definition)
                try:
                    description = definition.docstring(raw=True).strip()
                except Exception:
                    description = ''
                if not description and not hasattr(definition,
                                                   'get_line_code'):
                    # jedi returns an empty string for compiled objects
                    description = definition.docstring().strip()
            if definition.type == 'module':
                signature = definition.full_name
                try:
                    description = definition.docstring(raw=True).strip()
                except Exception:
                    description = ''
                if not description and hasattr(definition, 'get_line_code'):
                    # jedi returns an empty string for compiled objects
                    description = definition.docstring().strip()

            def_type = get_definition_type(definition)
            if def_type in ('function', 'method'):
                signature = 'def ' + signature
            elif def_type == 'class':
                signature = 'class ' + signature
            else:
                # TODO(keegan) vscode python uses the current word if definition.name is empty
                signature = definition.name

            # TODO(keegan) implement the rest of https://sourcegraph.com/github.com/DonJayamanne/pythonVSCode/-/blob/src/client/providers/hoverProvider.ts#L34
            results.append({
                "language": "python",
                "value": signature,
            })
            if description:
                results.append(description)

        if results:
            return {"contents": results}
        else:
            return {}

    def serve_definition(self, request, parent_span):
        params = request["params"]
        pos = params["position"]
        path = path_from_uri(params["textDocument"]["uri"])
        source = self.fs.open(path, parent_span)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(
            path=path,
            source=source,
            line=pos["line"] + 1,
            column=pos["character"],
            parent_span=parent_span
        )

        defs = LangServer.goto_definitions(script, request, parent_span)
        locs = []
        for d in defs:
            if not d.is_definition() or d.line is None or d.column is None:
                continue
            locs.append({
                # TODO(renfred) determine why d.module_path is empty.
                "uri": "file://" + (d.module_path or path),
                "range": {
                    "start": {
                        "line": d.line - 1,
                        "character": d.column,
                    },
                    "end": {
                        "line": d.line - 1,
                        "character": d.column + len(d.name),
                    },
                },
            })
        return locs

    def serve_references(self, request, parent_span):
        params = request["params"]
        pos = params["position"]
        path = path_from_uri(params["textDocument"]["uri"])
        source = self.fs.open(path, parent_span)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(
            path=path,
            source=source,
            line=pos["line"] + 1,
            column=pos["character"],
            parent_span=parent_span
        )

        usages = LangServer.usages(script, parent_span)
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

    def serve_symbols(self, request, parent_span):
        if self.all_symbols is None:
            self.all_symbols = workspace_symbols(self.fs, self.root_path, parent_span)

        params = request["params"]
        q, limit = params.get("query"), params.get("limit", 50)
        symbols = ((sym.score(q), sym) for sym in self.all_symbols)
        symbols = ((score, sym) for (score, sym) in symbols if score >= 0)
        symbols = sorted(symbols, reverse=True, key=lambda x: x[0])[:limit]

        return [s.json_object() for (_, s) in symbols]

    def serve_documentSymbols(self, request, parent_span):
        params = request["params"]
        path = path_from_uri(params["textDocument"]["uri"])
        source = self.fs.open(path, parent_span)
        return [s.json_object() for s in extract_symbols(source, path)]

    def serve_exit(self, request, parent_span):
        self.running = False

    def serve_default(self, request, parent_span):
        raise JSONRPC2Error(
            code=-32601,
            message="method {} not found".format(request["method"]))


class JSONRPC2Error(Exception):
    def __init__(self, code, message, data=None):
        self.code = code
        self.message = message
        self.data = data


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


class LangserverTCPTransport(socketserver.StreamRequestHandler):
    def handle(self):
        conn = JSONRPC2Connection(TCPReadWriter(self.rfile, self.wfile))
        s = LangServer(conn)
        s.run()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="")
    parser.add_argument(
        "--mode", default="stdio", help="communication (stdio|tcp)")
    parser.add_argument(
        "--addr", default=4389, help="server listen (tcp)", type=int)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--lightstep_project")
    parser.add_argument("--lightstep_token")

    args = parser.parse_args()

    logging.basicConfig(level=(logging.DEBUG if args.debug else logging.INFO))

    if args.lightstep_project and args.lightstep_token:
        Tracer.setup(args.lightstep_project, args.lightstep_token)

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
