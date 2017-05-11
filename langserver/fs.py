import base64
import os
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import List

from .tracer import Tracer
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

    def batch_open(self, paths):
        for path in paths:
            yield (path, self.open(path))

    def walk(self, top: str):
        dir = self.listdir(top)
        files, dirs = [], []
        for e in dir:
            if e.is_dir:
                dirs.append(os.path.join(top, e.name))
            else:
                files.append(os.path.join(top, e.name))
        yield from files
        for d in dirs:
            yield from self.walk(d)


class LocalFileSystem(FileSystem):
    def open(self, path, parent_span):
        return open(path).read()

    def listdir(self, path, parent_span):
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
    def open(self, path, parent_span):
        with Tracer.start_span("RemoteFileSystem.open", parent_span) as open_span:
            open_span.set_tag("path", path)
            resp = self.conn.send_request("textDocument/xcontent", {
                "textDocument": {
                    "uri": "file://" + path
                }
            })
            if "error" in resp:
                raise FileException(resp["error"])
            return resp["result"]["text"]

    @lru_cache(maxsize=128)
    def listdir(self, path, parent_span):
        with Tracer.start_span("RemoteFileSystem.listdir", parent_span) as list_span:
            list_span.set_tag("path", path)
            # TODO(keegan) Use workspace/xfiles + cache
            resp = self.conn.send_request("fs/readDir", path)
            if resp.get("error") is not None:
                raise FileException(resp["error"])
            entries = []
            for e in resp["result"]:
                entries.append(Entry(e["name"], e["dir"], e["size"]))
            return entries

    def walk(self, path):
        resp = self.conn.send_request("workspace/xfiles",
                                      {"base": "file://" + path})
        if "error" in resp:
            raise FileException(resp["error"])
        for doc in resp["result"]:
            uri = doc["uri"]
            if uri.startswith("file://"):
                yield uri[7:]
            else:
                yield uri

    def batch_open(self, paths, parent_span):
        with Tracer.start_span("RemoteFileSystem.batch_open", parent_span) as batch_open_span:
            # We need to read the iterator paths twice, so convert to list
            paths = list(paths)
            responses = self.conn.send_request_batch(("textDocument/xcontent", {
                "textDocument": {
                    "uri": "file://" + path
                }
            }) for path in paths)
            for path, resp in zip(paths, responses):
                if "error" in resp:
                    # Consume rest of generator to ensure resources are shutdown
                    for _ in responses:
                        pass
                    raise FileException(resp["error"])
                yield (path, resp["result"]["text"])
