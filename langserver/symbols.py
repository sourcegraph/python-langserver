import ast
import itertools
import multiprocessing
import logging

from enum import Enum


log = logging.getLogger(__name__)


class SymbolKind(Enum):
    """SymbolKind corresponds to the SymbolKind enum type found in the LSP spec."""
    File = 1
    Module = 2
    Namespace = 3
    Package = 4
    Class = 5
    Method = 6
    Property = 7
    Field = 8
    Constructor = 9
    Enum = 10
    Interface = 11
    Function = 12
    Variable = 13
    Constant = 14
    String = 15
    Number = 16
    Boolean = 17
    Array = 18


class Symbol:
    def __init__(self, name, kind, line, col, container=None, file=None):
        self.name = name
        self.kind = kind
        self.line = line
        self.col = col
        self.container = container
        self.file = file

    def score(self, query: str) -> int:
        """Score a symbol based on how well it matches a query.
        Useful for sorting."""
        score = 0
        if self.kind == SymbolKind.Class:
            score += 1
        if self.kind != SymbolKind.Variable:
            score += 1
        if self.container is None:
            score += 1
        if self.file and 'test' not in self.file:
            score += 5
        if query == "":
            return score
        min_score = score
        l_name, l_query = self.name.lower(), query.lower()
        if query == self.name:
            score += 10
        elif l_name == l_query:
            score += 8
        if self.name.startswith(query):
            score += 5
        elif l_name.startswith(l_query):
            score += 4
        if l_query in l_name:
            score += 2
        if self.container:
            if self.container.lower().startswith(l_query):
                score += 2
            if l_query == self.container.lower() + "." + l_name:
                score += 10
        if self.file and self.file.lower().startswith(l_query):
            score += 1
        if score <= min_score:
            score = -1
        return score

    def json_object(self):
        d = {
            "name": self.name,
            "kind": self.kind.value,
            "location": {
                "uri": "file://" + self.file,
                "range": {
                    "start": {
                        "line": self.line - 1,
                        "character": self.col,
                    },
                    "end": {
                        "line": self.line - 1,
                        "character": self.col + len(self.name),
                    }
                }
            },
        }
        if self.container is not None:
            d["containerName"] = self.container
        return d


def extract_symbols(source, path):
    """extract_symbols is a generator yielding symbols for source"""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        log.error("Error parsing Python file %s:%s -- %s: %s", path, e.lineno, e.msg, e.text)
        return

    s = SymbolVisitor()
    for j in s.visit(tree):
        j.file = path
        yield j


def extract_exported_symbols(source, path):
    is_exported = lambda s: not (s.name.startswith('_') or (s.container is not None and s.container.startswith('_')))
    return filter(is_exported, extract_symbols(source, path))


def workspace_symbols(fs, root_path, parent_span):
    "returns a list of all exported symbols under root_path in fs."
    py_paths = (path for path in fs.walk(root_path) if path.endswith(".py"))
    py_srces = fs.batch_open(py_paths, parent_span)
    with multiprocessing.Pool() as p:
        symbols_chunks = p.imap_unordered(
            _imap_extract_exported_symbols, py_srces, chunksize=10)
        symbols = list(itertools.chain.from_iterable(symbols_chunks))
    return symbols


# This exists purely for passing into imap
def _imap_extract_exported_symbols(args):
    path, src = args
    return list(extract_exported_symbols(src, path))


class SymbolVisitor:
    def visit_Module(self, node, container):
        # Modules is our global scope. Just visit all the children
        yield from self.generic_visit(node)

    def visit_ClassDef(self, node, container):
        yield Symbol(node.name, SymbolKind.Class, node.lineno, node.col_offset)

        # Visit all child symbols, but with container set to the class
        yield from self.generic_visit(node, container=node.name)

    def visit_FunctionDef(self, node, container):
        yield Symbol(
            node.name,
            SymbolKind.Function if container is None else SymbolKind.Method,
            node.lineno,
            node.col_offset,
            container=container)

    def visit_Assign(self, assign_node, container):
        for node in assign_node.targets:
            if not hasattr(node, "id"):
                continue
            yield Symbol(
                node.id,
                SymbolKind.Variable,
                node.lineno,
                node.col_offset,
                container=container)

    def visit_If(self, node, container):
        # If is often used provide different implementations for the same var. To avoid duplicate names, we only visit
        # the true body.
        for child in node.body:
            yield from self.visit(child, container)

    # Based on ast.NodeVisitor.visit
    def visit(self, node, container=None):
        # Two changes from ast.NodeVisitor.visit:
        # * Do not fallback to generic_visit (we only care about top-level)
        # * container optional argument
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, None)
        if visitor is not None:
            yield from visitor(node, container)

    # Based on ast.NodeVisitor.generic_visit
    def generic_visit(self, node, container=None):
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        yield from self.visit(item, container)
            elif isinstance(value, ast.AST):
                yield from self.visit(value, container)


