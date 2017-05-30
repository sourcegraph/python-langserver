import logging
import socketserver
import sys
import os
import traceback

import lightstep
import opentracing

from .config import GlobalConfig
from .fs import LocalFileSystem, RemoteFileSystem
from .jedi import RemoteJedi
from .jsonrpc import JSONRPC2Connection, ReadWriter, TCPReadWriter
from .workspace import Workspace
from .symbols import extract_symbols, workspace_symbols, targeted_symbol


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
        self.workspace = None

    def run(self):
        while self.running:
            try:
                request = self.conn.read_message()
                self.handle(request)
            except EOFError:
                break
            except Exception as e:
                log.error("Unexpected error: %s", e, exc_info=True)

    def handle(self, request):
        if "meta" in request:
            span_context = opentracing.tracer.extract(
                opentracing.Format.TEXT_MAP, request["meta"])
        else:
            span_context = None

        with opentracing.tracer.start_span(
                request.get("method", "UNKNOWN"),
                child_of=span_context) as span:
            request["span"] = span
            self.route_and_respond(request)

    def route_and_respond(self, request):
        log.info("REQUEST %s %s", request.get("id"), request.get("method"))

        noop = lambda *a: None
        handler = {
            "initialize": self.serve_initialize,
            "textDocument/hover": self.serve_hover,
            "textDocument/definition": self.serve_definition,
            "textDocument/xdefinition": self.serve_x_definition,
            "textDocument/references": self.serve_references,
            "textDocument/documentSymbol": self.serve_document_symbols,
            "workspace/symbol": self.serve_symbols,
            "workspace/xpackages": self.serve_x_packages,
            "workspace/xdependencies": self.serve_x_dependencies,
            "$/cancelRequest": noop,
            "shutdown": noop,
            "exit": self.serve_exit,
        }.get(request["method"], self.serve_default)

        # We handle notifications differently since we can't respond
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
            with opentracing.start_child_span(
                    request["span"], "send_response") as write_response_span:
                self.conn.write_response(request["id"], resp)

    def new_script(self, *args, **kwargs):
        return RemoteJedi(self.fs, self.workspace, self.root_path).new_script(*args, **kwargs)

    @staticmethod
    def goto_assignments(script, request):
        parent_span = request["span"]
        try:
            with opentracing.start_child_span(
                    parent_span, "Script.goto_assignments") as assn_span:
                return script.goto_assignments()
        except Exception as e:
            # TODO return these errors using JSONRPC properly. Doing it this way
            # initially for debugging purposes.
            log.error("Failed goto_assignments for %s", request, exc_info=True)
            parent_span.log_kv(
                {"error", "Failed goto_assignments for %s" % request})
        return []

    @staticmethod
    def goto_definitions(script, request):
        parent_span = request["span"]
        try:
            with opentracing.start_child_span(
                    parent_span, "Script.goto_definitions") as def_span:
                return script.goto_definitions()
        except Exception as e:
            # TODO return these errors using JSONRPC properly. Doing it this way
            # initially for debugging purposes.
            log.error("Failed goto_definitions for %s", request, exc_info=True)
            parent_span.log_kv(
                {"error", "Failed goto_definitions for %s" % request})
        return []

    @staticmethod
    def usages(script, parent_span):
        with opentracing.start_child_span(parent_span,
                                          "Script.usages") as usages_span:
            return script.usages()

    def serve_initialize(self, request):
        params = request["params"]
        self.root_path = path_from_uri(params["rootPath"])

        caps = params.get("capabilities", {})
        if caps.get("xcontentProvider") and caps.get("xfilesProvider"):
            # The client supports a remote fs
            self.fs = RemoteFileSystem(self.conn)
        else:
            self.fs = LocalFileSystem()

        self.workspace = Workspace(self.fs, self.root_path, params["originalRootPath"])

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
        parent_span = request.get("span", None)
        source = self.fs.open(path, parent_span)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(
            path=path,
            source=source,
            line=pos["line"] + 1,
            column=pos["character"],
            parent_span=parent_span)

        defs = LangServer.goto_definitions(script, request) or LangServer.goto_assignments(script, request)

        # The code from this point onwards is modified from the MIT licensed github.com/DonJayamanne/pythonVSCode

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
        with opentracing.start_child_span(
                parent_span, "accumulate_definitions") as accum_defs_span:
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
                    if not description and hasattr(definition,
                                                   'get_line_code'):
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

    def serve_definition(self, request):
        return list(filter(None, (d["location"] for d in self.serve_x_definition(request))))

    def serve_x_definition(self, request):
        params = request["params"]
        pos = params["position"]
        path = path_from_uri(params["textDocument"]["uri"])
        parent_span = request["span"]
        source = self.fs.open(path, parent_span)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(
            path=path,
            source=source,
            line=pos["line"] + 1,
            column=pos["character"],
            parent_span=parent_span)

        results = []
        defs = LangServer.goto_definitions(script, request) or LangServer.goto_assignments(script, request)
        if not defs:
            return results

        for d in defs:

            defining_module_path = d.module_path
            defining_module = self.workspace.get_module_by_path(defining_module_path)

            if not defining_module and (not d.is_definition() or d.line is None or d.column is None):
                continue

            symbol_locator = {"symbol": None, "location": None}

            if defining_module and defining_module.is_external and not defining_module.is_stdlib:
                # the module path doesn't map onto the repository structure because we're not fully installing
                # dependency packages, so don't include it in the symbol descriptor
                filename = os.path.basename(defining_module_path)
                symbol_name = ""
                symbol_kind = ""
                if d.description:
                    symbol_name, symbol_kind = self.name_and_kind(d.description)
                symbol_locator["symbol"] = {
                    "package": {
                        "name": defining_module.qualified_name.split(".")[0],
                    },
                    "name": symbol_name,
                    "container": defining_module.qualified_name,
                    "kind": symbol_kind,
                    "file": filename
                }

            elif defining_module and defining_module.is_stdlib:
                rel_path = os.path.relpath(defining_module_path, self.workspace.PYTHON_PATH)
                filename = os.path.basename(defining_module_path)
                symbol_name = ""
                symbol_kind = ""
                if d.description:
                    symbol_name, symbol_kind = self.name_and_kind(d.description)
                symbol_locator["symbol"] = {
                    "package": {
                        "name": "cpython",
                    },
                    "name": symbol_name,
                    "container": defining_module.qualified_name,
                    "kind": symbol_kind,
                    "path": os.path.join(GlobalConfig.STDLIB_SRC_PATH, rel_path),
                    "file": filename
                }

            else:
                symbol_locator["location"] = {
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
                }

            results.append(symbol_locator)
        return results

    def name_and_kind(self, description: str):
        parts = description.split(" ")
        if "=" in description:
            name = parts[0]
            kind = "="
        else:
            name = parts[1]
            kind = parts[0]
        return name, kind

    def serve_references(self, request):
        params = request["params"]
        pos = params["position"]
        path = path_from_uri(params["textDocument"]["uri"])
        parent_span = request["span"]
        source = self.fs.open(path, parent_span)
        if len(source.split("\n")[pos["line"]]) < pos["character"]:
            return {}
        script = self.new_script(
            path=path,
            source=source,
            line=pos["line"] + 1,
            column=pos["character"],
            parent_span=parent_span)

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

    def serve_symbols(self, request):
        parent_span = request["span"]
        params = request["params"]

        if "symbol" in params:
            return targeted_symbol(params["symbol"], self.fs, self.root_path, parent_span)

        if self.all_symbols is None:
            self.all_symbols = workspace_symbols(self.fs, self.root_path,
                                                 parent_span)

        q, limit = params.get("query"), params.get("limit", 50)
        symbols = ((sym.score(q), sym) for sym in self.all_symbols)
        symbols = ((score, sym) for (score, sym) in symbols if score >= 0)
        symbols = sorted(symbols, reverse=True, key=lambda x: x[0])[:limit]

        return [s.json_object() for (_, s) in symbols]

    def serve_document_symbols(self, request):
        params = request["params"]
        path = path_from_uri(params["textDocument"]["uri"])
        parent_span = request["span"]
        source = self.fs.open(path, parent_span)
        return [s.json_object() for s in extract_symbols(source, path)]

    def serve_x_packages(self, request):
        return self.workspace.get_package_information(request["span"])

    def serve_x_dependencies(self, request):
        return self.workspace.get_dependencies(request["span"])

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


class ForkingTCPServer(socketserver.ForkingMixIn, socketserver.TCPServer):
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
    parser.add_argument("--lightstep_token")
    parser.add_argument("--python_path")
    parser.add_argument("--pip_command")

    args = parser.parse_args()

    logging.basicConfig(level=(logging.DEBUG if args.debug else logging.INFO))

    if args.python_path:
        GlobalConfig.PYTHON_PATH = args.python_path
    if args.pip_command:
        GlobalConfig.PIP_COMMAND = args.pip_command

    log.info("Setting Python path defaulting to %s", GlobalConfig.PYTHON_PATH)

    # if args.lightstep_token isn't set, we'll fall back on the default no-op opentracing implementation
    if args.lightstep_token:
        opentracing.tracer = lightstep.Tracer(
            component_name="python-langserver",
            access_token=args.lightstep_token)

    if args.mode == "stdio":
        logging.info("Reading on stdin, writing on stdout")
        s = LangServer(conn=ReadWriter(sys.stdin, sys.stdout))
        s.run()
    elif args.mode == "tcp":
        host, addr = "0.0.0.0", args.addr
        logging.info("Accepting TCP connections on %s:%s", host, addr)
        ForkingTCPServer.allow_reuse_address = True
        ForkingTCPServer.daemon_threads = True
        s = ForkingTCPServer((host, addr), LangserverTCPTransport)
        try:
            s.serve_forever()
        finally:
            s.shutdown()


if __name__ == "__main__":
    main()
