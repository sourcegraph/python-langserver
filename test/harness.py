import langserver.langserver as langserver
import langserver.fs as fs

import opentracing


class Harness:

    def __init__(self, local_repo_path: str):
        self.langserver = langserver.LangServer(conn=None)
        self.local_repo_path = local_repo_path
        self.langserver.fs = fs.TestFileSystem(local_repo_path)
        self.id = 0

    def next_id(self):
        self.id = self.id + 1
        return self.id

    def request(self, method: str, params):
        return {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": method,
            "params": params,
            "span": opentracing.tracer.start_span()
        }

    @staticmethod
    def text_document_position_params(file: str, line: int, character: int):
        return {
            "textDocument": {
                "uri": file
            },
            "position": {
                "line": line,
                "character": character
            }
        }

    def initialize(self, original_root_path: str):
        params = {
            "rootPath": self.local_repo_path,
            "originalRootPath": original_root_path
        }
        request = self.request("initialize", params)
        return self.langserver.test_initialize(
            request, fs.TestFileSystem(self.local_repo_path))

    def exit(self):
        self.langserver.serve_exit({})

    def x_packages(self):
        request = self.request("workspace/xpackages", {})
        return self.langserver.serve_x_packages(request)

    def hover(self, file: str, line: int, character: int):
        params = self.text_document_position_params(file, line, character)
        request = self.request("textDocument/hover", params)
        return self.langserver.serve_hover(request)

    def definition(self, file: str, line: int, character: int):
        params = self.text_document_position_params(file, line, character)
        request = self.request("textDocument/definition", params)
        return self.langserver.serve_x_definition(request)

    def references(self, file: str, line: int, character: int):
        params = self.text_document_position_params(file, line, character)
        request = self.request("textDocument/references", params)
        return self.langserver.serve_references(request)

    def x_references(self, container: str, name: str):
        symbol = {"container": container, "name": name}
        params = {"query": symbol}
        request = self.request("workspace/xreferences", params)
        return self.langserver.serve_x_references(request)


# helper for printing test results so that they can be copied back into
# the test (i.e., when adding new tests)
def print_result(result):
    print("\nRESULT\n", result, "\n")
