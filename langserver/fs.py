import base64
from abc import ABC, abstractmethod

from langserver.jsonrpc import JSONRPC2Server

class FileException(Exception):
    pass

class FileSystem(ABC):
    @abstractmethod
    def open(path: str) -> str:
        pass

class LocalFileSystem(FileSystem):
    def open(self, path):
        return open(path).read()

class RemoteFileSystem(FileSystem):
    def __init__(self, server: JSONRPC2Server):
        self.server = server

    def open(self, path):
        resp = self.server.send_request("fs/readFile", path)
        if resp.get("error") is not None:
            raise FileException(resp["error"])
        return base64.b64decode(resp["result"]).decode("utf-8")

