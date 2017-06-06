"""
This module is used for x-references.
"""

import ast


class ReferenceFilteringVisitor(ast.NodeVisitor):
    """
    Check whether an AST contains an import for a given name. We use this to narrow down the set of files in which to
    search for global references.
    """
    def __init__(self, name=None):
        self.name = name
        self.result = False

    def visit_Module(self, node):
        self.generic_visit(node)

    def visit_Import(self, node):
        for n in node.names:
            if n.name and n.name.split(".")[0] == self.name:
                self.result = True
                break

    def visit_ImportFrom(self, node):
        if node.module and node.module.split(".")[0] == self.name:
            self.result = True

    # Based on ast.NodeVisitor.visit
    def visit(self, node):
        # One change from ast.NodeVisitor.visit: do not fallback to generic_visit (we only care about top-level)
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, None)
        if visitor is not None:
            visitor(node)


class ReferenceFindingVisitor(ast.NodeVisitor):
    def __init__(self, name=None, path=None):
        self.name = name
        self.path = path
        self.results = []

    def visit_Name(self, node):
        if node.id == self.name:
            self.results.append({"line": node.lineno-1, "character": node.col_offset, "path": self.path})

    def visit_Import(self, node):
        for n in node.names:
            if n.name and self.name in n.name.split("."):
                self.results.append({"line": node.lineno-1, "character": node.col_offset, "path": self.path})

    def visit_ImportFrom(self, node):
        if node.module and self.name in node.module.split("."):
            self.results.append({"line": node.lineno-1, "character": node.col_offset, "path": self.path})
        for n in node.names:
            if n.name == self.name:
                self.results.append({"line": node.lineno - 1, "character": node.col_offset, "path": self.path})


def get_references(module_name, symbol_name, fs, root_path, parent_span):
    for path, tree in filter_for_references(module_name, fs, root_path, parent_span):
        v = ReferenceFindingVisitor(symbol_name, path)
        v.visit(tree)
        if v.results:
            yield v.results


def filter_for_references(name, fs, root_path, parent_span):
    py_paths = (path for path in fs.walk(root_path) if path.endswith(".py"))

    py_srces = ((path, fs.open(path, parent_span)) for path in py_paths)

    # py_srces = fs.batch_open(py_paths, parent_span)

    for path_and_source in py_srces:
        path, source = path_and_source
        tree = _filter(name, source)
        if tree:
            yield path, tree


def _filter(name, source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    v = ReferenceFilteringVisitor(name)
    v.visit(tree)
    if v.result:
        return tree
    else:
        return None
