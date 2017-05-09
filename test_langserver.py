#!/usr/local/bin/python3

import os.path
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from langserver.symbols import extract_symbols

def test_extract_symbols():
    import json
    want = '''{"name": "MyClass", "kind": 5, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 0}}}}
{"name": "__init__", "kind": 6, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 2, "character": 4}, "end": {"line": 2, "character": 4}}}, "containerName": "MyClass"}
{"name": "foo", "kind": 6, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 5, "character": 4}, "end": {"line": 5, "character": 4}}}, "containerName": "MyClass"}
{"name": "_private", "kind": 6, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 10, "character": 4}, "end": {"line": 10, "character": 4}}}, "containerName": "MyClass"}
{"name": "baz", "kind": 12, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 13, "character": 0}, "end": {"line": 13, "character": 0}}}}
{"name": "X", "kind": 13, "location": {"uri": "file://example_file.py", "range": {"start": {"line": 16, "character": 0}, "end": {"line": 16, "character": 0}}}}'''
    symbols = extract_symbols(example_file, 'example_file.py')
    got = "\n".join(json.dumps(s.json_object()) for s in symbols)
    assert got == want

example_file = '''
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
'''