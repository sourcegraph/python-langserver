# Language server extensions for Visual Studio Code

A language server is responsible for statically analyzing source code, usually for a single language,
and providing answers to the following questions:

* given a location (a character offset in a file), what is the "hover tooltip" (summarizing the entity at that location)?
* given a location, what is the corresponding "jump-to-def" location (where the entity is declared)?
* given a location, what are all the locations where the entity at that location is referenced (including its declaration)?
* what are all the definitions (in a workspace) that a user can "jump-to" by name
  * these would typically be the types/classes/functions/methods appearing on documentation sites, "public" APIs, declarations indexed by ctags, "top-level" identifiers, etc. (i.e. not local variables)

To answer these questions, a language server must implement a subset of the
[Microsoft Language Server Protocol](https://github.com/Microsoft/language-server-protocol) (LSP).

## Required Methods

The method subset of LSP which must be implemented includes:

* [`initialize`](https://github.com/Microsoft/language-server-protocol/blob/master/protocol.md#initialize-request)
* [`textDocument/didOpen`](https://github.com/Microsoft/language-server-protocol/blob/master/protocol.md#didopentextdocument-notification)
* [`textDocument/definition`](https://github.com/Microsoft/language-server-protocol/blob/master/protocol.md#goto-definition-request)
* [`textDocument/hover`](https://github.com/Microsoft/language-server-protocol/blob/master/protocol.md#hover-request)
* [`textDocument/references`](https://github.com/Microsoft/language-server-protocol/blob/master/protocol.md#find-references-request)
* [`workspace/symbol`](https://github.com/Microsoft/language-server-protocol/blob/master/protocol.md#workspace-symbols-request)
* [`shutdown`](https://github.com/Microsoft/language-server-protocol/blob/master/protocol.md#shutdown-request)

## Definitions

1. A **workspace** is a directory tree containing source code files (rooted at the `rootPath` specified in the `initialize` request)
2. **language server** (or **LS**) is the generic name of a backend implementing LSP (or the subset shown above)
3. **LSP** is the name of the [protocol defined by Microsoft](https://github.com/Microsoft/language-server-protocol) for
clients to communicate with language servers

## Getting Started

- [Install Go](https://golang.org/doc/install) and [set up your workspace for Go development](https://golang.org/doc/code.html).
- Install the sample language server:
```bash
go get -u github.com/sourcegraph/langserver/langserver-sample
```
- Verify the sample language server works with your installation of VSCode:
```bash
cd vscode-client
npm install
npm run vscode -- $GOPATH/src/github.com/sourcegraph/langserver
```
- Open a plain text file (e.g. `vscode-client/License.txt`), hover over some text.

## Development

You will write a program which speaks LSP over stdin and stdout (and/or runs a TCP listener and speaks LSP over the socket).

You should test your language server using [VSCode](https://code.visualstudio.com/) as a reference client.
To wire your language server to VSCode, follow the [vscode-client README](https://github.com/sourcegraph/langserver/blob/master/vscode-client/README.md).

Your language server is expected to operate in memory and use a filesystem overlay. Once the language server receives
an `initialize` request, it will subsequently receive file sources and dependencies via `textDocument/didOpen`.
Use this method to construct the filesystem overlay. When the language server performs any operation that depends on a
file's contents, it should first try to read the contents from the overlay. If the file is not in the overlay, then the
language server should consult the file system.

It is OK and desirable to keep warm data structures/indexes in memory to speed up subsequent requests.

## Testing

For convenience, this project includes a REPL to make request to your language server over stdio (or a TCP connection):

```bash
go install ./lspcli
lspcli --root=/path/to/repo --mode=tcp # connect to a language server over TCP port 2088
lspcli --root=/path/to/repo --mode=tcp --addr=4444 # port 4444
lspcli --root=/path/to/repo --cmd=langserver-sample # spawn a subprocess and communicate over stdio
```

## Delivering

Deliver your language server with CI running a suite of test cases for `textDocument/hover`, `textDocument/definition`, `textDocument/references`, and
`workspace/symbol` requests against sample repositories of your choice.

Provide some additional information about your language server characteristics in the README:

- what are the memory requirements for sample (small/medium/large) workspaces?
- what are the performance characteristics of `textDocument/hover`, `textDocument/definition`, `textDocument/references`, and `workspace/symbol` requests?

Aim to meet these performance benchmarks:
- <500ms P95 latency for `textDocument/definition` and `textDocument/hover` requests
- <10s P95 latency for `textDocument/references` request
- <5s P95 latency for `workspace/symbol` request

## LSP Method Details

- `textDocument/hover` may return two types of `MarkedString`:
  - `language="text/html"`: a documentation string
  - `language="$LANG"`: a type signature
- `workspace/symbol` will be queried in two ways:
  - `query=""`: return all symbols for "jump-to" by name
    - NOTE: it's currently not possible to test this functionality directly within VSCode, as it only sends a `workspace/symbol` request for non-empty queries
  - `query="is:external-reference"`: return all references to declarations outside of the project (to dependencies, standard libraries, etc.)
    - NOTE: Always excludes vendored libraries, e.g. vendored Go packages, JS code inside a `node_modules` directory, etc.
  - `query="is:exported"`: return only 'exported' declarations (e.g. exclude private functions/vars/etc).
    - NOTE: Always excludes vendored libraries, e.g. vendored Go packages, JS code inside a `node_modules` directory, etc.

