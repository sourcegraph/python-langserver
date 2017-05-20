from .fs import FileSystem, LocalFileSystem
from .imports import get_imports
from typing import Dict, Set
import sys
import os
import os.path
import opentracing


class DummyFile:
    def __init__(self, contents):
        self.contents = contents

    def read(self):
        return self.contents

    def close(self):
        pass


class Module:
    def __init__(self,
                 name: str,
                 qualified_name: str,
                 path: str,
                 is_package: bool=False,
                 is_external: bool=False,
                 is_stdlib: bool=False):
        self.name = name
        self.qualified_name = qualified_name
        self.path = path
        self.is_package = is_package
        self.is_external = is_external
        self.is_stdlib = is_stdlib

    def __repr__(self):
        return "PythonModule({}, {})".format(self.name, self.path)


STDLIB_REPO_URL = "git://github.com/python/cpython"
STDLIB_SRC_PATH = "Lib"


class Workspace:

    def __init__(self, fs: FileSystem, project_root: str, original_root_path: str= ""):  # TODO: get url from init request

        self.project_packages = set()
        self.PROJECT_ROOT = project_root
        self.repo = None
        self.hash = None

        if original_root_path.startswith("git://") and "?" in original_root_path:
            repo_and_hash = original_root_path.split("?")
            self.repo = repo_and_hash[0]
            self.hash = repo_and_hash[1]

        self.is_stdlib = (self.repo == STDLIB_REPO_URL)

        if original_root_path.startswith("git://"):
            original_root_path = original_root_path[6:]

        # turn the original root path into something that can be used as a file/path name or cache key
        self.key = original_root_path.replace("/", ".").replace("\\", ".")
        if self.hash:
            self.key = ".".join((self.key, self.hash))

        self.PYTHON_ROOT = "/usr/lib/python3.5"  # TODO: point to whatever Python version the project wants
        self.PACKAGES_ROOT = "/tmp/python-dist/lib/python3.5/site-packages"  # TODO: point to workspace-specific folder

        self.fs = fs
        self.local_fs = LocalFileSystem()
        self.project = {}
        self.stdlib = {}
        self.dependencies = {}
        self.module_paths = {}

        self.index_project()

        for n in sys.builtin_module_names:
            self.stdlib[n] = None  # TODO: figure out how to provide code intelligence for compiled-in modules
        self.index_dependencies(self.stdlib, self.PYTHON_ROOT, is_stdlib=True)

        # TODO: do this part on-demand
        self.index_dependencies(self.dependencies, self.PACKAGES_ROOT)

    def index_dependencies(self,
                           index: Dict[str, Module],
                           library_path: str,
                           is_stdlib: bool=False,
                           breadcrumb: str=None):
        """
        Given a root library path (e.g., the Python root path or the dist-packages root path), this method traverses
        it recursively and indexes all the packages and modules contained therein. It constructs a mapping from the
        fully qualified module name to a Module object containing the metadata that Jedi needs.

        :param index: the dictionary that should be used to store this index (will be modified)
        :param library_path: the root path containing the modules and packages to be indexed
        :param is_stdlib: flag indicating whether this invocation is indexing the standard library
        :param breadcrumb: should be omitted by the caller; this method uses it to keep track of the fully qualified
        module name
        """
        for filename in os.listdir(library_path):

            basename, extension = os.path.splitext(filename)
            if filename == "__init__.py":
                # we're inside a folder whose name is the package name, so the breadcrumb is the qualified name
                qualified_name = breadcrumb
            elif extension == ".egg":
                # it's a Python egg; discard the shell and go deeper, which means using the breadcrumb as-is
                # TODO: might need to process the config files if we run into edge cases
                qualified_name = breadcrumb
            elif breadcrumb:
                # otherwise add the filename to the breadcrumb
                qualified_name = ".".join((breadcrumb, basename))
            else:
                qualified_name = basename

            if os.path.isdir(os.path.join(library_path, filename)):
                # recursively index the folder
                self.index_dependencies(index, os.path.join(library_path, filename), is_stdlib, qualified_name)
            elif filename == "__init__.py":
                # we're already inside a package
                module_name = os.path.basename(library_path)
                the_module = Module(module_name,
                                    qualified_name,
                                    os.path.join(library_path, filename),
                                    True,
                                    True,
                                    is_stdlib)
                index[qualified_name] = the_module
                self.module_paths[the_module.path] = the_module
            elif extension == ".py":
                # just a regular non-package module
                the_module = Module(basename,
                                    qualified_name,
                                    os.path.join(library_path, filename),
                                    False,
                                    True,
                                    is_stdlib)
                index[qualified_name] = the_module
                self.module_paths[the_module.path] = the_module

    def index_project(self):
        """
        This method traverses all the project files (starting with self.PROJECT_ROOT) and indexes all the packages and
        modules contained therein. It constructs a mapping from the fully qualified module name to a Module object
        containing the metadata that Jedi needs. Because it only has a flat list of paths/uris to work with (as
        opposed to being able to walk the file tree top-down), it does some extra work to figure out the qualified
        names of each module.
        """
        all_paths = list(self.fs.walk(self.PROJECT_ROOT))

        # pre-compute the set of all packages in this project -- this will be useful a bit later, when trying to
        # figure out each module's qualified name
        package_paths = {}
        for path in all_paths:
            folder, filename = os.path.split(path)
            if filename == "__init__.py":
                package_paths[folder] = True

        # now index all modules and packages, taking care to compute their qualified names correctly (can be tricky
        # depending on how the folders are nested, and whether they have '__init__.py's or not
        for path in all_paths:
            folder, filename = os.path.split(path)
            basename, ext = os.path.splitext(filename)
            if filename == "__init__.py":
                parent, this = os.path.split(folder)
                # check if this is a root package in this project
                if os.path.dirname(parent).endswith("/"):
                    parent_parent = os.path.basename(parent)
                    if parent_parent:
                        self.project_packages.add(os.path.basename(parent))
            elif filename.endswith(".py"):
                parent = folder
                this = basename
            else:
                continue
            qualified_name_components = [this]
            # A module's qualified name should only contain the names of its enclosing folders that are packages (i.e.,
            # that contain an '__init__.py'), not the names of *all* its enclosing folders. Hence, the following loop
            # only accumulates qualified name components until it encounters a folder that isn't in the pre-computed
            # set of packages.
            while parent and parent != "/" and parent in package_paths:
                parent, this = os.path.split(parent)
                qualified_name_components.append(this)
            qualified_name_components.reverse()
            qualified_name = ".".join(qualified_name_components)
            if filename == "__init__.py":
                module_name = os.path.basename(folder)
                the_module = Module(module_name, qualified_name, path, True)
                self.project[qualified_name] = the_module
                self.module_paths[the_module.path] = the_module
            elif ext == ".py" and not basename.startswith("__") and not basename.endswith("__"):
                the_module = Module(basename, qualified_name, path)
                self.project[qualified_name] = the_module
                self.module_paths[the_module.path] = the_module

    def find_stdlib_module(self, qualified_name: str) -> Module:
        return self.stdlib.get(qualified_name, None)

    def find_project_module(self, qualified_name: str) -> Module:
        return self.project.get(qualified_name, None)

    def find_external_module(self, qualified_name: str) -> Module:
        return self.dependencies.get(qualified_name, None)

    def open_module_file(self, the_module: Module, parent_span: opentracing.Span) -> str:
        if the_module.is_external:
            return self.local_fs.open(the_module.path, parent_span)
        else:
            return self.fs.open(the_module.path, parent_span)

    def get_module_by_path(self, path: str) -> Module:
        return self.module_paths.get(path, None)

    def get_dependencies(self, parent_span: opentracing.Span) -> list:
        top_level_stdlib = {p.split(".")[0] for p in self.stdlib}
        top_level_imports = get_imports(self.fs, self.PROJECT_ROOT, parent_span)
        stdlib_imports = top_level_imports & top_level_stdlib
        external_imports = top_level_imports - top_level_stdlib - self.project_packages
        dependencies = [{"attributes": {"name": n}} for n in external_imports]
        if stdlib_imports:
            dependencies.append({
                "attributes": {
                    "name": "cpython",
                    "repoURL": "git://github.com/python/cpython"
                }
            })
        return dependencies

    def get_package_information(self, parent_span: opentracing.Span) -> list:
        return [
            {
                "package": {"name": p},
                "dependencies": self.get_dependencies(parent_span)  # multiple packages in the project share the same dependencies
            } for p in self.project_packages
        ]

    @staticmethod
    def get_top_level_package_names(index: Dict[str, Module]) -> Set[str]:
        return {name.split(".")[0] for name in index}
