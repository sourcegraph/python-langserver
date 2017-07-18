import ast
import os
import os.path
import logging


log = logging.getLogger(__name__)


class SetupVisitor(ast.NodeVisitor):
    """
    The purpose of this class is to crawl over a project's setup.py and statically extract the configuration info that
    we need in order to infer package names, exports, dependencies, etc.
    """
    def __init__(self, workspace, path):
        self.workspace = workspace
        self.name = None
        self.packages = set()
        self.requirements = set()
        self.bindings = {}
        self.path = path

    def visit_Call(self, node):
        """
        Look for calls to `setup` or `find_packages`.
        :param node: the function call node that we're visiting
        :return: None
        """
        func_name = self.get_func_name(node.func)
        if func_name not in ("setup", "find_packages"):
            return

        args, kwds = self.get_func_args(node)

        if func_name == "find_packages":
            where = os.path.dirname(self.path)
            exclude = ()
            include = ("*",)
            # TODO(aaron): relativize the incoming `where` arg?
            if len(args) > 0:
                where = os.path.join(args[0])
            elif "where" in kwds:
                where = os.path.join(kwds["where"])
            if len(args) > 1:
                exclude = args[1]
            elif "exclude" in kwds:
                exclude = kwds["exclude"]
            if len(args) > 2:
                include = args[2]
            elif "include" in kwds:
                include = kwds["include"]
            return {p for p in self.workspace.find_packages(where, exclude, include)}

        if func_name == "setup":
            self.name = kwds.get("name", None)
            self.packages = kwds.get("packages", None)
            self.requirements = {r for r in kwds.get("install_requires", set())}

    def visit_Assign(self, node):
        """
        Keep track of assignments of vars to literal values, references, and calls to find_packages. Stores everything
        in a single dict and doesn't keep track of nested scopes.
        :param node: the assignment node that we're visiting
        :return:
        """
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
        """
        Takes the left-hand-side of an assignment and figures out the name that's being assigned.
        :param node: the left-hand-side of the assignment
        :return:
        """
        if type(node) is ast.Name:
            return node.id
        elif type(node) is ast.NameConstant:
            return node.value
        elif type(node) is ast.Attribute:
            return node.attr
        else:
            return None

    def eval_rhs(self, node):
        if type(node) is ast.Name:
            return self.bindings.get(node.id, None)
        elif type(node) is ast.NameConstant:
            return self.bindings.get(node.value, None)
        elif type(node) is ast.Attribute:
            return self.bindings.get(node.attr, None)
        elif type(node) is ast.Call:  # only handle calls to find_packages
            return self.visit_Call(node)
        else:
            try:
                return ast.literal_eval(node)
            except ValueError:
                return None

    @staticmethod
    def get_func_name(node):
        func_name = None
        if type(node) is ast.NameConstant:
            func_name = node.value
        elif type(node) is ast.Name:
            func_name = node.id
        elif type(node) is ast.Attribute:
            func_name = node.attr
        return func_name

    def get_func_args(self, node):

        if type(node) is not ast.Call:
            return None

        args = [self.eval_rhs(arg) for arg in node.args]
        kwds = {kwd.arg: self.eval_rhs(kwd.value) for kwd in node.keywords}

        return args, kwds


def upset(src, path, workspace):
    tree = ast.parse(src, "setup.py")
    visitor = SetupVisitor(workspace, path)
    visitor.visit(tree)
    return visitor
