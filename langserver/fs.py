import base64
import os
from abc import ABC, abstractmethod

from langserver.jsonrpc import JSONRPC2Server

class FileException(Exception):
    pass

class FileSystem(ABC):
    @abstractmethod
    def open(path: str) -> str:
        pass

    @abstractmethod
    def listdir(path: str):
        pass

class LocalFileSystem(FileSystem):
    def open(self, path):
        return open(path).read()

    def listdir(self, path):
        raise NotImplementedError # TODO(renfred)

class RemoteFileSystem(FileSystem):
    def __init__(self, server: JSONRPC2Server):
        self.server = server

    def open(self, path):
        resp = self.server.send_request("fs/readFile", path)
        if resp.get("error") is not None:
            raise FileException(resp["error"])
        return base64.b64decode(resp["result"]).decode("utf-8")

    def listdir(self, path):
        resp = self.server.send_request("fs/readDir", path)
        if resp.get("error") is not None:
            raise FileException(resp["error"])
        return resp["result"]

