import base64
import os
import os.path
from abc import ABC, abstractmethod

import opentracing
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
    def open(path: str, parent_span) -> str:
        pass

    @abstractmethod
    def listdir(path: str, parent_span) -> List[str]:
        pass

    def batch_open(self, paths, parent_span):
        for path in paths:
            yield (path, self.open(path))

    def walk(self, top: str):
        dir = self.listdir(top)
        files, dirs = [], []
        for e in dir:
            if os.path.isdir(e):
                dirs.append(os.path.join(top, e))
            else:
                files.append(os.path.join(top, e))
        yield from files
        for d in dirs:
            yield from self.walk(d)


class LocalFileSystem(FileSystem):
    def open(self, path, parent_span=None):
        with open(path) as open_file:
            return open_file.read()

    def listdir(self, path, parent_span=None):
        entries = []
        names = os.listdir(path)
        # TODO: prepend `path` to each name?
        return names
        # for n in names:
        #     p = os.path.join(path, n)
        #     entries.append(Entry(n, os.path.isdir(p), os.path.getsize(p)))
        # return entries


class RemoteFileSystem(FileSystem):
    def __init__(self, conn: JSONRPC2Connection):
        self.conn = conn

    def open(self, path, parent_span=None):
        if parent_span is None:
            resp = self.conn.send_request("textDocument/xcontent", {
                "textDocument": {
                    "uri": "file://" + path
                }
            })
            if "error" in resp:
                raise FileException(resp["error"])
            return resp["result"]["text"]

        with opentracing.start_child_span(
                parent_span, "RemoteFileSystem.open") as open_span:
            open_span.set_tag("path", path)
            resp = self.conn.send_request("textDocument/xcontent", {
                "textDocument": {
                    "uri": "file://" + path
                }
            })
            if "error" in resp:
                raise FileException(resp["error"])
            return resp["result"]["text"]

    def listdir(self, path, parent_span=None):
        if parent_span is None:
            return self._listdir(path)

        with opentracing.start_child_span(
                parent_span, "RemoteFileSystem.listdir") as list_span:
            list_span.set_tag("path", path)
            # TODO(keegan) Use workspace/xfiles + cache
            return self._listdir(path)

    def _listdir(self, path):
        resp = self.conn.send_request("fs/readDir", path)
        if resp.get("error") is not None:
            raise FileException(resp["error"])
        entries = []
        for e in resp["result"]:
            entries.append(e["name"])
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
        with opentracing.start_child_span(
                parent_span, "RemoteFileSystem.batch_open") as batch_open_span:
            # We need to read the iterator paths twice, so convert to list
            paths = list(paths)
            responses = self.conn.send_request_batch(("textDocument/xcontent",
                                                      {
                                                          "textDocument": {
                                                              "uri":
                                                              "file://" + path
                                                          }
                                                      }) for path in paths)
            for path, resp in zip(paths, responses):
                if "error" in resp:
                    # Consume rest of generator to ensure resources are shutdown
                    for _ in responses:
                        pass
                    raise FileException(resp["error"])
                yield (path, resp["result"]["text"])


class InMemoryFileSystem(FileSystem):
    def __init__(self, contents):
        self.contents = contents

    def open(self, path: str, parent_span) -> str:
        if path in self.contents:
            return self.contents[path]
        raise FileException('File not found ' + path)

    def listdir(self, path: str, parent_span) -> List[Entry]:
        if path.endswith('/'):
            path = path[:-1]
        path_parts = path.split('/')
        entries = {}
        for p, v in self.contents.items():
            if not p.startswith(path):
                continue
            p_parts = p.split('/')
            if len(p_parts) <= len(path_parts):
                continue
            if p_parts[len(path_parts) - 1] != path_parts[-1]:
                continue
            name = p_parts[len(path_parts)]
            if name in entries:
                continue
            is_dir = len(p_parts) > len(path_parts) + 1
            size = 0 if is_dir else len(v)
            entries[name] = Entry(name, is_dir, size)
        return entries.values()


# TODO(aaron): determine whether this extra filesystem is really necessary, or if we could have just used a local fs
# I suspect not, because the new workspace indexing/importing code wasn't written with a local fs in mind
class TestFileSystem(FileSystem):
    def __init__(self, local_root_path: str):
        self.root = os.path.abspath(local_root_path)

    def open(self, path: str, parent_span=None):
        if os.path.isabs(path):
            path = os.path.join(self.root, os.path.relpath(path, "/"))
        else:
            path = os.path.join(self.root, path)
        with open(path) as open_file:
            return open_file.read()

    def batch_open(self, paths, parent_span):
        for path in paths:
            yield (path, self.open(path))

    def listdir(self, path: str, parent_span=None):
        path = os.path.abspath(path)
        if not path.startswith(self.root):  # need this check for namespace imports, for which we get a relative path
            if path.startswith("/"):
                path = path[1:]
            path = os.path.join(self.root, path)
        return [os.path.join(path, p) for p in os.listdir(path)]

    def walk(self, top: str):
        yield from (os.path.join("/", p) for p in self._walk(top))

    def _walk(self, top: str):
        dir = self.listdir(top)
        files, dirs = [], []
        for e in dir:
            if os.path.isdir(e):
                dirs.append(os.path.relpath(e, self.root))
            else:
                files.append(os.path.relpath(e, self.root))
        yield from files
        for d in dirs:
            yield from self._walk(os.path.join(self.root, d))
