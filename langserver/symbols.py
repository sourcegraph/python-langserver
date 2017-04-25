import astroid as ast
import json
from astroid.exceptions import AstroidError
from enum import Enum


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
                        "character": self.col,
                    }
                }
            },
        }
        if self.container is not None:
            d["containerName"] = self.container
        return d


class SymbolEmitter:
    """
    SymbolEmitter provides methods for generating symbol information for selected
    exported symbols in a given Python source file.
    """

    def __init__(self, source, file=None):
        self.source = source
        self.file = file

    def symbols(self):
        try:
            t = ast.parse(self.source)
        except AstroidError:
            # If we fail to parse the AST, ignore the file
            return []
        return list(self._visit(t))

    def _visit(self, node):
        s = self.node_to_symbol(node)
        if s is not None:
            yield s
        for c in node.get_children():
            yield from self._visit(c)

    def node_to_symbol(self, node):
        # Classes
        if isinstance(node, ast.scoped_nodes.ClassDef):
            return Symbol(
                node.name,
                SymbolKind.Class,
                node.lineno,
                node.col_offset,
                file=self.file)
        # Functions/Methods
        elif isinstance(node, ast.scoped_nodes.FunctionDef):
            if node.is_method():
                return Symbol(
                    node.name,
                    SymbolKind.Method,
                    node.lineno,
                    node.col_offset,
                    container=node.parent.name,
                    file=self.file)
            else:
                return Symbol(
                    node.name,
                    SymbolKind.Function,
                    node.lineno,
                    node.col_offset,
                    file=self.file)
        # Variables
        elif isinstance(node, ast.node_classes.AssignName):
            # Global variables
            if isinstance(node.scope(), ast.scoped_nodes.Module):
                return Symbol(
                    node.name,
                    SymbolKind.Variable,
                    node.lineno,
                    node.col_offset,
                    file=self.file)
