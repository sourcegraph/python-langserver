import ast
import logging


log = logging.getLogger(__name__)


class SetupVisitor(ast.NodeVisitor):
    """
    The purpose of this class is to crawl over a project's setup.py and extract the configuration info that we need in
    order to infer package names, exports, dependencies, etc.
    """
    def __init__(self, workspace):
        self.workspace = workspace
        self.name = None
        self.packages = set()
        self.requirements = set()
        self.bindings = {}

    def visit_Call(self, node):
        """
        Look for a call to `setup`. In doing so, we might also eval calls to `find_packages`.
        :param node: the function call node that we're visiting
        :return: None
        """
        func_name = self.get_func_name(node.func)

        if func_name != "setup":
            return

        args, kwds = self.get_func_args(node.func)

        self.name = kwds.get("name", None)
        self.packages = kwds.get("packages", None)
        self.requirements = {r for r in kwds.get("install_requires", set())}

    def visit_Assign(self, node):
        vars = [self.eval_lhs(var) for var in node.targets]
        vals = self.eval_rhs(node.value)
        if len(vars) == 1:
            assns = zip(vars, [vals])
        elif type(vals) in (list, tuple, set, dict):
            assns = zip(vars, vals)
        else:
            return
        for var, val in assns:
            self.bindings[var] = val

    @staticmethod
    def eval_lhs(node):
        if type(node) is ast.Name:
            return node.id.to_string()
        elif type(node) is ast.NameConstant:
            return node.value.to_string()
        elif type(node) is ast.Attribute:
            return node.attr.to_string()
        else:
            return None

    def eval_rhs(self, node):
        if type(node) is ast.Name:
            return self.bindings.get(node.id.to_string(), None)
        elif type(node) is ast.NameConstant:
            return self.bindings.get(node.value.to_string(), None)
        elif type(node) is ast.Attribute:
            return self.bindings.get(node.attr.to_string(), None)
        elif type(node) is ast.Call:  # only handle calls to find_packages
            func_name = self.get_func_name(node)
            if func_name != "find_packages":
                return None
            else:
                args, kwds = self.get_func_args(node)
                return {p for p in self.workspace.find_packages(*args, **kwds)}
        else:
            return ast.literal_eval(node)

    @staticmethod
    def get_func_name(node):

        if type(node) is not ast.Call:
            return None

        func_name = None
        if type(node) is ast.NameConstant:
            func_name = node.value.to_string()
        elif type(node) is ast.Name:
            func_name = node.id.to_string()
        elif type(node) is ast.Attribute:
            func_name = node.attr

        return func_name

    def get_func_args(self, node):

        if type(node) is not ast.Call:
            return None

        args = [self.eval_rhs(arg) for arg in node.args]
        kwds = {kwd.arg.to_string(): self.eval_rhs(kwd.value) for kwd in node.keywords}

        return args, kwds


def upset(src, workspace):
    tree = ast.parse(src, "setup.py")
    visitor = SetupVisitor(workspace)
    visitor.visit(tree)
    return visitor
