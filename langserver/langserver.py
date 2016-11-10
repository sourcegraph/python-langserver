import sys
import json
import jedi

class JSONRPC2Error(Exception):
    pass

def log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def path_from_uri(uri):
    _, path = uri.split("file://", 1)
    return path

def read_header_content_length(line):
    if len(line) < 2 or line[-2:] != "\r\n":
        raise JSONRPC2Error("Line endings must be \\r\\n")
    if line.startswith("Content-Length: "):
        _, value = line.split("Content-Length: ")
        value = value.strip()
        try:
            return int(value)
        except ValueError:
            raise JSONRPC2Error("Invalid Content-Length header: {}".format(value))

def write_response(id, result):
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
    sys.stdout.write(response)
    sys.stdout.flush()
    log("RESPONSE: ", response)

def read_messages():
    while True:
        line = sys.stdin.readline()
        length = read_header_content_length(line)
        body = sys.stdin.read(length+2) # TODO(renfred): why the off-by-two?
        request = json.loads(body)
        log("REQUEST: ", length, request)
        if request["method"] == "initialize":
            write_response(request["id"], {
                "capabilities": {
                    # "textDocumentSync": 1,
                    "hoverProvider": True,
                    "definitionProvider": True,
                    "referencesProvider": True,
                    # "workspaceSymbolProvider": True TODO
                }
            })

        elif request["method"] == "textDocument/hover":
            write_response(request["id"], handle_hover(request))

        elif request["method"] == "textDocument/definition":
            write_response(request["id"], handle_definition(request))

        elif request["method"] == "textDocument/references":
            write_response(request["id"], handle_references(request))

def handle_hover(request):
    params = request["params"]
    pos = params["position"]
    path = path_from_uri(params["textDocument"]["uri"])
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

def handle_definition(request):
    params = request["params"]
    pos = params["position"]
    path = path_from_uri(params["textDocument"]["uri"])
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

def handle_references(request):
    params = request["params"]
    pos = params["position"]
    path = path_from_uri(params["textDocument"]["uri"])
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
    log("Reading on stdin, writing on stdout")
    read_messages()

if __name__ == "__main__":
    main()
