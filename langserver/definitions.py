from .symbols import SymbolKind, Symbol
import ast
import os
import logging


log = logging.getLogger(__name__)


class TargetedSymbolVisitor:
    """
    The purpose of this class is to take a SymbolDescriptor (typically the result of a preceding x-definition request)
    and perform a more precise symbol search based on the extra metadata available in the descriptor.
    """
    def __init__(self, name, kind, path):
        self.name = name
        self.kind = kind
        # the AST nodes for modules don't contain their name, so we have to infer it from the file or folder name
        folder, file = os.path.split(path)
        if file == "__init__.py":
            self.module = os.path.basename(folder)
        else:
            basename, _ = os.path.splitext(file)
            self.module = basename

    def visit_Module(self, node, container):
        if self.kind == "module" and self.name == self.module:
            yield Symbol(
                self.module,
                SymbolKind.Module,
                1,  # hard-code the position because module nodes don't have position attributes
                0,
                container=container
            )
            # if we found the desired module, we're done
        else:
            # else visit all the children
            yield from self.generic_visit(node)

    def visit_ImportFrom(self, node, container):
        # this handles the case where imported symbols are re-exported; an xj2d sometimes needs to land here
        for n in node.names:
            if n.name == self.name:
                yield Symbol(
                    n.name,
                    SymbolKind.Variable,
                    node.lineno,
                    node.col_offset,
                    container=container
                )
                break
            if n.asname and self.name == n.asname:
                yield Symbol(
                    n.asname,
                    SymbolKind.Variable,
                    node.lineno,
                    node.col_offset,
                    container=container
                )
                break

    def visit_Import(self, node, container):
        for n in node.names:
            if n.name and self.name in n.name.split("."):
                yield Symbol(
                    n.name,
                    SymbolKind.Variable,
                    node.lineno,
                    node.col_offset,
                    container=container
                )
            if n.asname and self.name == n.asname:
                yield Symbol(
                    n.asname,
                    SymbolKind.Variable,
                    node.lineno,
                    node.col_offset,
                    container=container
                )

    def visit_ClassDef(self, node, container):
        if self.kind == "class" and self.name == node.name:
            yield Symbol(node.name, SymbolKind.Class, node.lineno, node.col_offset)
        else:
            yield from self.generic_visit(node, container=node.name)

    def visit_FunctionDef(self, node, container):
        if self.kind == "instance" and self.name == container and node.name == "__init__":
            yield Symbol(
                node.name,
                SymbolKind.Constructor,
                node.lineno,
                node.col_offset,
                container=container
            )
        elif self.kind == "def" and self.name == node.name:
            yield Symbol(
                node.name,
                SymbolKind.Function if container is None else SymbolKind.Method,
                node.lineno,
                node.col_offset,
                container=container
            )

    def visit_Assign(self, assign_node, container):
        for node in assign_node.targets:
            if not hasattr(node, "id"):
                continue
            if self.kind == "=" and self.name == node.id:
                yield Symbol(
                    node.id,
                    SymbolKind.Variable,
                    node.lineno,
                    node.col_offset,
                    container=container)
                return

    def visit_If(self, node, container):
        # If is often used provide different implementations for the same var. To avoid duplicate names, we only visit
        # the true body.
        for child in node.body:
            yield from self.visit(child, container)

    # variables are sometimes initialized conditionally in try/catch blocks too
    def visit_Try(self, node, container):
        for child in node.body:
            yield from self.visit(child, container)
        for child in node.handlers:
            yield from self.visit(child, container)
        for child in node.orelse:
            yield from self.visit(child, container)
        for child in node.finalbody:
            yield from self.visit(child, container)

    def visit_ExceptHandler(self, node, container):
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


def targeted_symbol(symbol_descriptor, fs, root_path, parent_span):
    if "path" in symbol_descriptor:
        # exact path
        file_filter = "/" + symbol_descriptor["path"]
    else:
        # just the filename
        file_filter = "/" + symbol_descriptor["file"]
    paths = (path for path in fs.walk(root_path) if path.endswith(file_filter))
    symbols = []
    for path in paths:
        source = fs.open(path, parent_span)
        try:
            tree = ast.parse(source, path)
        except SyntaxError as e:
            log.error("Error parsing Python file %s:%s -- %s: %s", path, e.lineno, e.msg, e.text)
            continue
        visitor = TargetedSymbolVisitor(symbol_descriptor["name"], symbol_descriptor["kind"], path)
        for sym in visitor.visit(tree):
            sym.file = path
            symbols.append(sym.json_object())
    return symbols
