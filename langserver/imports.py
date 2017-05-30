import ast
import itertools
import multiprocessing


def get_imports(fs, root_path, parent_span):
    # TODO: consider crawling over the main project files only; ignore examples, tests, etc
    py_paths = (path for path in fs.walk(root_path) if path.endswith(".py"))
    py_srces = fs.batch_open(py_paths, parent_span)
    with multiprocessing.Pool() as p:
        import_chunks = p.imap_unordered(
            _imap_extract_imports, py_srces, chunksize=10)
        imports = {i.split(".")[0] for i in itertools.chain.from_iterable(import_chunks)}
    return imports


def _imap_extract_imports(args):
    path, src = args
    return set(extract_imports(src, path))


def extract_imports(source, path):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return

    v = ImportVisitor()
    for i in v.visit(tree):
        yield i


class ImportVisitor:

    def visit_Module(self, node, container):
        # Modules is our global scope. Just visit all the children
        yield from self.generic_visit(node)

    def visit_Import(self, node, container):
        for n in node.names:
            yield n.name

    def visit_ImportFrom(self, node, container):
        if not node.level:  # we only care about top-level imports, and definitely want to ignore internal imports
            yield node.module

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
