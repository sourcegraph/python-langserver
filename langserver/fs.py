import base64
import os
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import List

from .jsonrpc import JSONRPC2Connection


class FileException(Exception):
    pass


class Entry:
    """Generic representation of a directory entry."""

    def __init__(self, name, is_dir, size):
        self.name = name
        self.is_dir = is_dir
        self.size = size


class FileSystem(ABC):
    @abstractmethod
    def open(path: str) -> str:
        pass

    @abstractmethod
    def listdir(path: str) -> List[Entry]:
        pass

    def walk(self, top: str):
        dir = self.listdir(top)
        files, dirs = [], []
        for e in dir:
            if e.is_dir:
                dirs.append(os.path.join(top, e.name))
            else:
                files.append(os.path.join(top, e.name))
        yield top, dirs, files
        for d in dirs:
            yield from self.walk(d)


class LocalFileSystem(FileSystem):
    def open(self, path):
        return open(path).read()

    def listdir(self, path):
        entries = []
        names = os.listdir(path)
        for n in names:
            p = os.path.join(path, n)
            entries.append(Entry(n, os.path.isdir(p), os.path.getsize(p)))
        return entries


class RemoteFileSystem(FileSystem):
    def __init__(self, conn: JSONRPC2Connection):
        self.conn = conn

    @lru_cache(maxsize=128)
    def open(self, path):
        resp = self.conn.send_request("fs/readFile", path)
        if resp.get("error") is not None:
            raise FileException(resp["error"])
        return base64.b64decode(resp["result"]).decode("utf-8")

    @lru_cache(maxsize=128)
    def listdir(self, path):
        resp = self.conn.send_request("fs/readDir", path)
        if resp.get("error") is not None:
            raise FileException(resp["error"])
        entries = []
        for e in resp["result"]:
            entries.append(Entry(e["name"], e["dir"], e["size"]))
        return entries
