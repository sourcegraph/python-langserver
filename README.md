# Python language server

[![Build Status](https://travis-ci.org/sourcegraph/python-langserver.svg?branch=master)](https://travis-ci.org/sourcegraph/python-langserver)

**Note: This language server is currently in the early stages of active development and not all features are yet supported. We encourage desktop users to use https://github.com/palantir/python-language-server instead.**

This is a language server for Python that adheres to the [Language Server Protocol (LSP)](https://github.com/Microsoft/language-server-protocol/blob/master/protocol.md). It uses [Jedi](https://github.com/davidhalter/jedi) to perform source code analysis. Python versions 2.x and 3.x are supported.

## Getting started

You'll need Python version 3.6 or greater or [pyenv](https://github.com/pyenv/pyenv) installed. You will also need [pipenv](https://github.com/pypa/pipenv) installed:

1.  `pipenv install`
2.  `pipenv run python python-langserver.py --mode=tcp --addr=2087`

To try it in [Visual Studio Code](https://code.visualstudio.com), install the [vscode-client](https://github.com/sourcegraph/langserver/tree/master/vscode-client) extension and then open up a `.py` file.

## Tests

Run `make test`.

The tests require `pytest`. Note that some tests may fail if you're using `virtualenv` instead of the system Python.

Ensure you're using the correct Python version for this project (3.6.4). Using an incorrect version may cause local failures for tests related to the Python standard library. Use [`pyenv`](https://github.com/pyenv/pyenv) to easily switch to the correct version:

```
pyenv install
pyenv local # should show 3.6.4
pyenv version # should show 3.6.4 - you're good to go!
```
