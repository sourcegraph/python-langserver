# Python language server

---

> NOTE: This project is no longer being maintained or in active development. See the [Sourcegraph fork of Microsoft's Python language server](https://github.com/sourcegraph/python-language-server).

---

[![Build Status](https://travis-ci.org/sourcegraph/python-langserver.svg?branch=master)](https://travis-ci.org/sourcegraph/python-langserver)

This is a language server for Python that adheres to the [Language Server Protocol (LSP)](https://github.com/Microsoft/language-server-protocol/blob/master/protocol.md). It uses [Jedi](https://github.com/davidhalter/jedi) to perform source code analysis. Python versions 2.x and 3.x are supported.

## Automatic Dependency Installation

### Configuring `pip`

`python-langserver` uses `pip` to fetch dependencies. To configure the behavior of `pip`, you can supply the `pipArgs` [`initalizationOption` field inside the `initalize` request parameters](https://microsoft.github.io/language-server-protocol/specification#initialize). `pipArgs` specifies a list of arguments to add to the invocation of `pip`, for example:

```Typescript
InitializeParams {
	//...
	"initializationOptions": {
        "pipArgs": [
            "--index-url=https://python.example.com",
            "--extra-index-url=https://pypi.python.org/simple"
        ]
        // ...
    }
}
```

This will tell `pip` to use `https://python.example.com` as its base package index and `https://pypi.python.org/simple` as an extra package index, as described in 
[the pip documentation](https://pip.pypa.io/en/stable/reference/pip_wheel/#index-url).

*Note, when using this language server with Sourcegraph - you can set the `initializationOptions` in your site configuration:*

```Javascript

{
    // ...
    "langservers": [
        {
            "language": "python",
            "initializationOptions": {
                "pipArgs": [
                    "--index-url=https://python.example.com",
                    "--extra-index-url=https://pypi.python.org/simple"
                ]
            }
        }
    ]
    // ...
}
```

### Inference of Package Names

The language server will not run `setup.py` or `pip install`. When it encounters an import, it tries to infer the package name and run `pip download`. (This also avoids running the downloaded package's `setup.py`.) This is expected to work as long as the name of the package on PyPI (or your private package index) is the same as the name that's imported in the source code.

## Development

### Getting started

You'll need Python version 3.6 or greater or [pyenv](https://github.com/pyenv/pyenv) installed. You will also need [pipenv](https://github.com/pypa/pipenv) installed:

1. `pipenv install`
2. `pipenv run python python-langserver.py --mode=tcp --addr=2087`

To try it in [Visual Studio Code](https://code.visualstudio.com), install the [vscode-client](https://github.com/sourcegraph/langserver/tree/master/vscode-client) extension and then open up a `.py` file.

### Tests

Run `make test`.

The tests require `pytest`. Note that some tests may fail if you're using `virtualenv` instead of the system Python.
