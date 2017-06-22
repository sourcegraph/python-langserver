import langserver.langserver as langserver
import langserver.fs as fs

import os
import os.path

import opentracing


class TestFileSystem(fs.FileSystem):
    def __init__(self, local_root_path: str):
        self.root = local_root_path

    def open(self, path: str, parent_span=None):
        with open(os.path.join(self.root, path)) as open_file:
            return open_file.read()

    def listdir(self, path: str, parent_span=None):
        return os.listdir(os.path.join(self.root, path))


class TestHarness:

    def __init__(self, local_repo_path: str):
        self.langserver = langserver.LangServer(conn=None)
        self.local_repo_path = local_repo_path
        self.langserver.fs = TestFileSystem(local_repo_path)
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

    def initialize(self):
        params = {
            "rootPath": self.local_repo_path
        }
        request = self.request("initialize", params)
        return self.langserver.serve_initialize(request)

    def hover(self, file: str, line: int, character: int):
        params = self.text_document_position_params(file, line, character)
        request = self.request("textDocument/hover", params)
        return self.langserver.serve_hover(request)

    def definition(self, file: str, line: int, character: int):
        params = self.text_document_position_params(file, line, character)
        request = self.request("textDocument/definition", params)
        return self.langserver.serve_x_definition(request)
