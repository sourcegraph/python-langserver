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
    '/c.py':
    '''
class C(object):
    def bar(self):
        foo = ""
        printf(foo)
        return str("This is a string literal")
''',
})


def test_extract_symbols():
    import json
    example_file = FS.open("/example_file.py", parent_span=None)
    want = '''{"kind": 5, "location": {"range": {"end": {"character": 7, "line": 1}, "start": {"character": 0, "line": 1}}, "uri": "file://example_file.py"}, "name": "MyClass"}
{"containerName": "MyClass", "kind": 6, "location": {"range": {"end": {"character": 12, "line": 2}, "start": {"character": 4, "line": 2}}, "uri": "file://example_file.py"}, "name": "__init__"}
{"containerName": "MyClass", "kind": 6, "location": {"range": {"end": {"character": 7, "line": 5}, "start": {"character": 4, "line": 5}}, "uri": "file://example_file.py"}, "name": "foo"}
{"containerName": "MyClass", "kind": 6, "location": {"range": {"end": {"character": 12, "line": 10}, "start": {"character": 4, "line": 10}}, "uri": "file://example_file.py"}, "name": "_private"}
{"kind": 12, "location": {"range": {"end": {"character": 3, "line": 13}, "start": {"character": 0, "line": 13}}, "uri": "file://example_file.py"}, "name": "baz"}
{"kind": 13, "location": {"range": {"end": {"character": 1, "line": 16}, "start": {"character": 0, "line": 16}}, "uri": "file://example_file.py"}, "name": "X"}'''
    symbols = extract_symbols(example_file, 'example_file.py')
    got = "\n".join(json.dumps(s.json_object(), sort_keys=True)
                    for s in symbols)
    assert got == want


def test_hover_on_def():
    h = hover('/a.py', 1, 7)
    assert h == {
        'contents': [{
            'language': 'python',
            'value': 'class A(param type(self))'
        }, 'A doc string']
    }


def test_hover_on_string_literal():
    h = hover('/c.py', 5, 21)
    assert h == {}  # expect no hover on a string literal


def test_hover_on_string_variable():
    h = hover('/c.py', 4, 15)
    assert h == {'contents': [{'language': 'python', 'value': 'str'}]}


def test_hover_on_str():
    h = hover('/c.py', 5, 16)
    assert h == {
        'contents': [{'language': 'python', 'value': 'class str(param object)'},
                     "str(object='') -> str\n"
                     'str(bytes_or_buffer[, encoding[, errors]]) -> str\n'
                     '\n'
                     'Create a new string object from the given object. If encoding '
                     'or\n'
                     'errors is specified, then the object must expose a data buffer\n'
                     'that will be decoded using the given encoding and error '
                     'handler.\n'
                     'Otherwise, returns the result of object.__str__() (if defined)\n'
                     'or repr(object).\n'
                     'encoding defaults to sys.getdefaultencoding().\n'
                     "errors defaults to 'strict'."]
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
