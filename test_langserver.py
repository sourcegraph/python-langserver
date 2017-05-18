#!/usr/local/bin/python3

import os.path
import sys

import opentracing
import pytest

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from langserver.fs import InMemoryFileSystem
from langserver.langserver import LangServer
from langserver.symbols import extract_symbols

FS = InMemoryFileSystem({
    '/example_file.py':
    '''
class MyClass(object):
    def __init__(self):
        pass

    def foo(self):
        def bar():
            pass
        pass

    def _private(self):
        pass
    
def baz():
    pass

X = "hi"
''',
    '/a.py':
    '''
class A:
    "A doc string"
    pass
''',
    '/b.py':
    '''
import fnmatch
from .a import A
if __name__ == '__main__':
    A()
    print(fnmatch.fnmatchcase("test","t*"))
''',
})


def test_extract_symbols():
    import json
    example_file = FS.open("/example_file.py", parent_span=None)
    want = '''{"name": "MyClass", "kind": 5, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 0}}}}
{"name": "__init__", "kind": 6, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 2, "character": 4}, "end": {"line": 2, "character": 4}}}, "containerName": "MyClass"}
{"name": "foo", "kind": 6, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 5, "character": 4}, "end": {"line": 5, "character": 4}}}, "containerName": "MyClass"}
{"name": "_private", "kind": 6, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 10, "character": 4}, "end": {"line": 10, "character": 4}}}, "containerName": "MyClass"}
{"name": "baz", "kind": 12, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 13, "character": 0}, "end": {"line": 13, "character": 0}}}}
{"name": "X", "kind": 13, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 16, "character": 0}, "end": {"line": 16, "character": 0}}}}'''
    symbols = extract_symbols(example_file, 'example_file.py')
    got = "\n".join(json.dumps(s.json_object()) for s in symbols)
    assert got == want


def test_hover_on_def():
    h = hover('/a.py', 1, 7)
    assert h == {
        'contents': [{
            'language': 'python',
            'value': 'class A(param type(self))'
        }, 'A doc string']
    }


@pytest.mark.skip(reason="Failing")
def test_hover_another_file():
    h = hover('/b.py', 4, 5)
    assert h == {
        'contents': [{
            'language': 'python',
            'value': 'class A(param type(self))'
        }, 'A doc string']
    }


#@pytest.mark.skip(reason="Failing")
def test_hover_stdlib():
    h = hover('/b.py', 5, 23)
    assert h == {
        'contents':
        [{
            'language': 'python',
            'value': 'def fnmatchcase(param name, param pat)'
        },
         "Test whether FILENAME matches PATTERN, including case.\n\nThis is a version of fnmatch() which doesn't case-normalize\nits arguments."
         ]
    }


def hover(path, line, character):
    server = LangServer(conn=None)
    server.fs = FS
    server.root_path = '/'
    return server.serve_hover({
        "params": {
            "textDocument": {
                "uri": "file://" + path
            },
            "position": {
                "line": line,
                "character": character,
            },
        },
        "span": opentracing.tracer.start_span()
    })


def test_inmemory_fs():
    contents = {
        "/a": "a",
        "/aa": "aa",
        "/b/b": "bb",
        "/b/c/d/e": "bcde",
        "/bb/b": "bbb",
    }
    fs = InMemoryFileSystem(contents)
    for path, v in contents.items():
        assert fs.open(path, parent_span=None) == v
    dirs = {
        "/": ["a", "aa", "b", "bb"],
        "/b": ["b", "c"],
        "/b/c": ["d"],
        "/bb": ["b"],
    }
    for d, want in dirs.items():
        want = sorted(want)
        got = sorted([e.name for e in fs.listdir(d, parent_span=None)])
        assert got == want
