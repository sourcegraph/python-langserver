import sys
import json

class JSONRPC2Error(Exception):
    pass

def log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

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
    log("Reading on stdin, writing on stdout")
    while True:
        line = sys.stdin.readline()
        length = read_header_content_length(line)
        body = sys.stdin.read(length+2) # TODO(renfred): why the off-by-two?
        request = json.loads(body)
        log("REQUEST: ", length, request)
        if request["method"] == "initialize":
            write_response(request["id"], {
                "capabilities": {
                    "textDocumentSync": 1,
                    "hoverProvider": True,
                    "definitionProvider": True,
                    "referencesProvider": True,
                    "workspaceSymbolProvider": True
                }
            })
        elif request["method"] == "textDocument/hover":
            pos = request["params"]["position"]
            write_response(request["id"], {
                "contents": [{"language":"markdown", "value": "Hello from python!"}],
                "range": {
                    "start": {"line": pos["line"], "character": pos["character"]-3},
                    "end": {"line": pos["line"], "character": pos["character"]+3},
                }
            })

def main():
    read_messages()

if __name__ == "__main__":
    main()
