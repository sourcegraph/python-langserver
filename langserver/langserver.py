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
from .symbols import extract_symbols, workspace_symbols
from .definitions import targeted_symbol
from .references import get_references
from .clone_workspace import CloneWorkspace, ModuleKind

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
        self.streaming = True

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
        if "meta" in request and isinstance(
                request["meta"], dict) and len(request["meta"]) > 0:
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

        def noop(*args):
            return None

        handler = {
            "initialize": self.serve_initialize,
            "textDocument/hover": self.serve_hover,
            "textDocument/definition": self.serve_definition,
            "textDocument/xdefinition": self.serve_x_definition,
            "textDocument/references": self.serve_references,
            "workspace/xreferences": self.serve_x_references,
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
                    request["span"], "send_response"):
                self.conn.write_response(request["id"], resp)

    def new_script(self, *args, **kwargs):
        return RemoteJedi(self.fs, self.workspace, self.root_path).new_script(
            *args, **kwargs)

    @staticmethod
    def goto_assignments(script, request):
        parent_span = request["span"]
        try:
            with opentracing.start_child_span(
                    parent_span, "Script.goto_assignments"):
                return script.goto_assignments()
        except Exception as e:
            # TODO return these errors using JSONRPC properly. Doing it
            # this way initially for debugging purposes.
            log.error("Failed goto_assignments for %s", request, exc_info=True)
            parent_span.log_kv(
                {"error", "Failed goto_assignments for %s" % request})
        return []

    @staticmethod
    def goto_definitions(script, request):
        parent_span = request["span"]
        try:
            with opentracing.start_child_span(
                    parent_span, "Script.goto_definitions"):
                return script.goto_definitions()
        except Exception as e:
            # TODO return these errors using JSONRPC properly. Doing it
            # this way initially for debugging purposes.
            log.error("Failed goto_definitions for %s", request, exc_info=True)
            parent_span.log_kv(
                {"error", "Failed goto_definitions for %s" % request})
        return []

    @staticmethod
    def usages(script, parent_span):
        with opentracing.start_child_span(parent_span,
                                          "Script.usages"):
            return script.usages()

    def serve_initialize(self, request):
        params = request["params"]
        self.root_path = path_from_uri(
            params.get("rootUri") or params.get("rootPath") or "")

        caps = params.get("capabilities", {})
        if caps.get("xcontentProvider") and caps.get("xfilesProvider"):
            # The client supports a remote fs
            self.fs = RemoteFileSystem(self.conn)
        else:
            self.fs = LocalFileSystem()

        pip_args = []
        if "initializationOptions" in params:
            initOps = params["initializationOptions"]
            if isinstance(initOps, dict) and "pipArgs" in initOps:
                p = initOps["pipArgs"]
                if isinstance(p, list):
                    pip_args = p
                else:
                    log.error("pipArgs (%s) found, but was not a list, so ignoring", str(p))

        # Sourcegraph also passes in a rootUri which has commit information
        originalRootUri = params.get("originalRootUri") or params.get(
            "originalRootPath") or ""
        self.workspace = Workspace(self.fs, self.root_path, originalRootUri, pip_args)

        return {
            "capabilities": {
                "hoverProvider": True,
                "definitionProvider": True,
                "referencesProvider": True,
                "documentSymbolProvider": True,
                "workspaceSymbolProvider": True,
                "streaming": True,
            }
        }

    # TODO(aaron): find a better way to create a langserver/workspace that
    # uses a TestFileSystem
    def test_initialize(self, request, fs):
        params = request["params"]
        self.root_path = path_from_uri(params["rootPath"])

        self.fs = fs
        self.streaming = False
        self.workspace = CloneWorkspace(self.fs, self.root_path,
                                        params["originalRootPath"])

        return {
            "capabilities": {
                "hoverProvider": True,
                "definitionProvider": True,
                "referencesProvider": True,
                "documentSymbolProvider": True,
                "workspaceSymbolProvider": True,
                "streaming": False,
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

        # get the Jedi Definition instances from which to extract the hover
        # information. We filter out string literal Definitions
        # (they are useless and distracting), which have exactly one
        # Definition named 'str', while preserving Definitions
        # for variables with inferred 'str' types and references to the builtin
        # `str` function.
        defs = LangServer.goto_definitions(script, request)
        if (len(defs) == 1 and defs[0].full_name == 'str' and
                defs[0].in_builtin_module() and defs[0].type == 'instance'):
            if len(LangServer.goto_assignments(script, request)) == 0:
                # omit string literal Definitions
                defs = []
        elif len(defs) == 0:
            defs = LangServer.goto_assignments(script, request)

        # The code from this point onwards is modified from the MIT licensed
        # github.com/DonJayamanne/pythonVSCode

        def generate_signature(completion):
            if completion.type in ['module'
                                   ] or not hasattr(completion, 'params'):
                return ''
            return '%s(%s)' % (completion.name,
                               ', '.join(p.description
                                         for p in completion.params if p))

        def get_definition_type(definition):
            definition.in_builtin_module
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
                parent_span, "accumulate_definitions"):
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
                    try:
                        signature = definition.full_name
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
                    # TODO(keegan) vscode python uses the current word if
                    # definition.name is empty
                    signature = definition.name

                # TODO(keegan) implement the rest of
                # https://sourcegraph.com/github.com/DonJayamanne/pythonVSCode/-/blob/src/client/providers/hoverProvider.ts#L34
                results.append({
                    "language": "python",
                    "value": signature,
                })
                if description:
                    results.append(description)
                elif definition.type == "param":
                    results.append("parameter `" + definition.name + "`")
                elif definition.type == "statement":
                    results.append("variable `" + definition.name + "`")

        if results:
            return {"contents": results}
        else:
            return {}

    def serve_definition(self, request):
        return list(
            filter(None, (d["location"]
                          for d in self.serve_x_definition(request))))

    def serve_x_definition(self, request):
        params = request["params"]
        pos = params["position"]
        path = path_from_uri(params["textDocument"]["uri"])
        # will be useful for filtering out circular/useless definitions
        pos["path"] = path
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
        defs = []
        defs.extend(LangServer.goto_definitions(script, request))
        defs.extend(LangServer.goto_assignments(script, request))
        if not defs:
            return results

        for d in defs:
            kind, module_path = ModuleKind.UNKNOWN, ""
            if d.module_path:
                kind, module_path = self.workspace.get_module_info(
                    d.module_path)

            if (not d.is_definition() or
                    d.line is None or d.column is None):
                continue

            symbol_locator = {"symbol": None, "location": None}

            if kind is not ModuleKind.UNKNOWN:
                if kind == ModuleKind.STANDARD_LIBRARY:
                    filename = module_path.name
                    symbol_name = ""
                    symbol_kind = ""
                    if d.description:
                        symbol_name, symbol_kind = LangServer.name_and_kind(
                            d.description)
                    symbol_locator["symbol"] = {
                        "package": {
                            "name": "cpython",
                        },
                        "name": symbol_name,
                        "container": d.full_name,
                        "kind": symbol_kind,
                        "path": str(GlobalConfig.STDLIB_SRC_PATH / module_path),
                        "file": filename
                    }
                else:
                    # the module path doesn't map onto the repository structure
                    # because we're not fully installing
                    # dependency packages, so don't include it in the symbol
                    # descriptor
                    filename = module_path.name
                    symbol_name = ""
                    symbol_kind = ""
                    if d.description:
                        symbol_name, symbol_kind = LangServer.name_and_kind(
                            d.description)
                    symbol_locator["symbol"] = {
                        "package": {
                            "name": d.full_name.split(".")[0],
                        },
                        "name": symbol_name,
                        "container": d.full_name,
                        "kind": symbol_kind,
                        "file": filename
                    }

            if (d.is_definition() and
                    d.line is not None and d.column is not None):
                location = {
                    # TODO(renfred) determine why d.module_path is empty.
                    "uri": "file://" + (str(module_path) or path),
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
                # add a position hint in case this eventually gets passed to an
                # operation that could use it
                if symbol_locator["symbol"]:
                    symbol_locator["symbol"]["position"] = location["range"][
                        "start"]

                # set the full location if the definition is in this workspace
                if not kind in [ModuleKind.UNKNOWN, ModuleKind.EXTERNAL_DEPENDENCY]:
                    symbol_locator["location"] = location

            results.append(symbol_locator)

        unique_results = []
        for result in results:
            if result not in unique_results:
                unique_results.append(result)

        # if there's more than one definition, go ahead and remove the ones
        # that are the same as the input position
        if len(unique_results) > 1:
            unique_results = [
                ur for ur in unique_results
                if not LangServer.is_circular(pos, ur["location"])
            ]
        return unique_results

    @staticmethod
    def is_circular(reference, definition):
        """Takes a reference location and a definition location, and determines
        whether they're the same (and hence useless).

        We need to do this because getting the definition of an import
        (using Jedi's goto_assignments method) sometimes returns that
        same import. We filter out such cases and fall back on
        goto_definitions.
        """
        if not reference or not definition:
            return False
        if reference["path"] != path_from_uri(definition["uri"]):
            return False
        if definition["range"]["start"]["line"] == 0 \
                and definition["range"]["end"]["line"] == 0 \
                and definition["range"]["start"]["character"] == 0:
            # if the definition is at the very beginning of the same file,
            # then we've almost certainly jumped to the beginning of the
            # module that we're already inside of
            return True
        if reference["line"] < definition["range"]["start"]["line"] \
                or reference["line"] > definition["range"]["end"]["line"]:
            return False
        if reference["character"] < definition["range"]["start"]["character"] \
                or reference["character"] > definition["range"]["end"]["character"]:
            return False
        return True

    @staticmethod
    def name_and_kind(description: str):
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
        limit = params.get("limit", 200)
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
        if len(usages) > limit:
            usages = usages[:limit]

        refs = []
        partial_initializer = {
            "id": request["id"],
            "patch": [{
                "op": "add",
                "path": "",
                "value": []
            }]
        }
        self.conn.send_notification(
            "$/partialResult", partial_initializer) if self.streaming else None
        json_patch = []
        # package_cache_path = os.path.abspath(self.workspace.PACKAGES_PATH)
        for u in usages:
            u.module_path = self.workspace.from_cache_path(u.module_path)
            if u.is_definition():
                continue
            # filter out any results from files that are cached on the local fs
            # if u.module_path.startswith(package_cache_path):
            #     continue
            if u.module_path.startswith(self.workspace.PYTHON_PATH):
                continue
            location = {
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
            }
            refs.append(location)
            patch_op = {
                "op": "add",
                "path": "/-",
                "value": location,
            }
            json_patch.append(patch_op)
        partial_result = {
            "id": request["id"],
            "patch": json_patch,
        }
        self.conn.send_notification("$/partialResult",
                                    partial_result) if self.streaming else None
        return refs

    def serve_x_references(self, request):
        parent_span = request["span"]
        params = request["params"]
        limit = params.get("limit", 200)
        symbol = params["query"]
        if not symbol:
            return []

        package_name = symbol["container"].split(".")[0]
        symbol_name = symbol["name"]

        refs = []
        partial_initializer = {
            "id": request["id"],
            "patch": [{
                "op": "add",
                "path": "",
                "value": []
            }]
        }
        self.conn.send_notification(
            "$/partialResult", partial_initializer) if self.streaming else None
        # We can't use Jedi to get x-refs because we only have a symbol descriptor,
        # not a source location and source file. I tried fetching the package that's
        # mentioned in the symbol descriptor and providing the source of the
        # definition for Jedi, but that didn't seem to work, maybe because the fetched
        # package is in the local FS cache, whereas the project files are handled by the remote FS.
        # Anyway, unless we want to dig further into Jedi or rewrite the FS abstraction, it's
        # easier to manually parse the source files and search the ASTs. We can still use Jedi to
        # eliminate false positives by ensuring that each returned reference has a definition that
        # matches the symbol descriptor.
        for ref_batch in get_references(package_name, symbol_name, self.fs,
                                        self.root_path, parent_span):
            json_patch = []
            for r in ref_batch:
                location = {
                    "uri": "file://" + r["path"],
                    "range": {
                        "start": {
                            "line": r["line"],
                            "character": r["character"],
                        },
                        "end": {
                            "line": r["line"],
                            "character": r["character"] + len(symbol_name)
                        }
                    }
                }
                ref_info = {
                    "reference": location,
                    "symbol": symbol,
                }
                refs.append(ref_info)
                patch_op = {
                    "op": "add",
                    "path": "/-",
                    "value": ref_info,
                }
                json_patch.append(patch_op)
                if len(refs) >= limit:
                    break
            partial_result = {
                "id": request["id"],
                "patch": json_patch,
            }
            self.conn.send_notification(
                "$/partialResult", partial_result) if self.streaming else None
            if len(refs) >= limit:
                break

        return refs

    def serve_symbols(self, request):
        parent_span = request["span"]
        params = request["params"]

        if "symbol" in params:
            return targeted_symbol(params["symbol"], self.fs, self.root_path,
                                   parent_span)

        if self.all_symbols is None:
            self.all_symbols = workspace_symbols(self.fs, self.root_path,
                                                 parent_span)

        q, limit = params.get("query"), params.get("limit", 50)
        symbols = ((sym.score(q), sym) for sym in self.all_symbols)
        symbols = ((score, sym) for (score, sym) in symbols if score >= 0)
        symbols = sorted(symbols, reverse=True, key=lambda x: x[0])[:limit]

        result = [s.json_object() for (_, s) in symbols]
        return result

    def serve_document_symbols(self, request):
        params = request["params"]
        path = path_from_uri(params["textDocument"]["uri"])
        parent_span = request["span"]
        source = self.fs.open(path, parent_span)
        return [s.json_object() for s in extract_symbols(source, path)]

    def serve_x_packages(self, request):
        return self.workspace.get_package_information()

    def serve_x_dependencies(self, request):
        return self.workspace.get_dependencies(request["span"])

    def serve_exit(self, request):
        self.workspace.cleanup()
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
    parser.add_argument("--lightstep_token", default=os.environ.get("LIGHTSTEP_ACCESS_TOKEN"))
    parser.add_argument("--python_path")

    args = parser.parse_args()

    logging.basicConfig(level=(logging.DEBUG if args.debug else logging.INFO))

    if args.python_path:
        GlobalConfig.PYTHON_PATH = args.python_path

    log.info("Setting Python path to %s", GlobalConfig.PYTHON_PATH)

    # if args.lightstep_token isn't set, we'll fall back on the default no-op
    # opentracing implementation
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
