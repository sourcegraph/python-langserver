# Python Language Server

Language server which talks LSP via JSONRPC for Python.

## Current State

This project is a mixed language server implementation in Golang (JSONRPC2 wrapper) and Python 3 (script to call [Jedi](https://jedi.readthedocs.io/en/latest/index.html)) with limited set of LSP.

**This server currently does not take care of workspace or virtual environment.**

### Supported LSP methods

- `initialize`
- `shutdown`
- `textDocument/hover`
- `textDocument/definition`: for internal definitions
- `textDocument/references`: for internal references

## Getting Started

As in early stage, this only works wtih our [vscode-client](https://github.com/sourcegraph/sourcegraph/tree/master/lang/vscode-client) extension, and not field tested for integration with main Sourcegraph app.

Make sure you have installed:

1. Go
2. Python3
3. Jedi

In order to debug with VSCode, you need to:

1. Compile `langserver-python` to a place inside `$PATH` (e.g. `$GOPATH/bin`).
2. Symbolic link `.bin/langserver-python.py` to a place inside `$PATH` (e.g. `$GOPATH/bin`).

## Performance

Meets [p95 requirements of Universe](https://github.com/sourcegraph/sourcegraph/issues/470) for [Reddit](https://github.com/reddit/reddit) which has about 80k loc in Python.