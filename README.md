# Python language server

**Note: This language server is currently in the early stages of active development and not all features are yet supported. We encourage desktop users to use https://github.com/palantir/python-language-server instead.**

This is a language server for Python that adheres to the [Language Server Protocol (LSP)](https://github.com/Microsoft/language-server-protocol/blob/master/protocol.md). It uses [Jedi](https://github.com/davidhalter/jedi) to perform source code analysis. Python versions 2.x and 3.x are supported.

## Getting started

You'll need Python version 3.5 or greater or [pyenv](https://github.com/pyenv/pyenv) installed. You will also need [pipenv](https://github.com/pypa/pipenv) installed:

1. `pipenv install`
2. `pipenv run python-langserver.py --mode=tcp --addr=2087`

To try it in [Visual Studio Code](https://code.visualstudio.com), install the [vscode-client](https://github.com/sourcegraph/langserver/tree/master/vscode-client) extension and then open up a `.py` file.

## Tests

Run `make test`.

The tests require `pytest`. Note that some tests may fail if you're using `virtualenv` instead of the system Python.
