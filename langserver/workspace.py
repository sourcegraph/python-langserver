from .config import GlobalConfig
from .fs import FileSystem, LocalFileSystem
from .imports import get_imports
from .fetch import fetch_dependency
from typing import Dict, Set, List

import logging
import sys
import os
import os.path
import shutil
import threading
import opentracing
import jedi._compatibility


log = logging.getLogger(__name__)


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
                 is_stdlib: bool=False,
                 is_native: bool=False,
                 is_namespace_package: bool=False):
        self.name = name
        self.qualified_name = qualified_name
        self.path = path
        self.is_package = is_package
        self.is_external = is_external
        self.is_stdlib = is_stdlib
        self.is_native = is_native
        self.is_namespace_package = is_namespace_package

    def __repr__(self):
        return "PythonModule({}, {})".format(self.name, self.path)


class Workspace:

    def __init__(self, fs: FileSystem, project_root: str, original_root_path: str= ""):

        self.project_packages = set()
        self.PROJECT_ROOT = project_root
        self.repo = None
        self.hash = None

        if original_root_path.startswith("git://") and "?" in original_root_path:
            repo_and_hash = original_root_path.split("?")
            self.repo = repo_and_hash[0]
            original_root_path = self.repo
            self.hash = repo_and_hash[1]

        self.is_stdlib = (self.repo == GlobalConfig.STDLIB_REPO_URL)

        if original_root_path.startswith("git://"):
            original_root_path = original_root_path[6:]

        # turn the original root path into something that can be used as a file/path name or cache key
        self.key = original_root_path.replace("/", ".").replace("\\", ".")
        if self.hash:
            self.key = ".".join((self.key, self.hash))

        self.PYTHON_PATH = GlobalConfig.PYTHON_PATH  # TODO: allow different Python versions per project/workspace
        self.PACKAGES_PATH = os.path.join(GlobalConfig.PACKAGES_PARENT, self.key)
        log.debug("Setting Python path to %s", self.PYTHON_PATH)
        log.debug("Setting package path to %s", self.PACKAGES_PATH)

        self.fs = fs
        self.local_fs = LocalFileSystem()
        self.source_paths = {path for path in self.fs.walk(self.PROJECT_ROOT) if path.endswith(".py")}
        self.project = {}
        self.stdlib = {}
        self.dependencies = {}
        self.module_paths = {}
        # keep track of which package folders have been indexed, since we fetch and index new folders on-demand
        self.indexed_folders = set()
        self.indexing_lock = threading.Lock()
        # keep track of which packages we've tried to fetch, so we don't keep trying if they were unfetchable
        self.fetched = set()

        self.index_project()

        for n in sys.builtin_module_names:
            self.stdlib[n] = "native"  # TODO: figure out how to provide code intelligence for compiled-in modules
        if "nt" not in self.stdlib:
            self.stdlib["nt"] = "native"  # this is missing on non-Windows systems; add it so we don't try to fetch it

        if os.path.exists(self.PYTHON_PATH):
            log.debug("Indexing standard library at %s", self.PYTHON_PATH)
            self.index_dependencies(self.stdlib, self.PYTHON_PATH, is_stdlib=True)
        else:
            log.warning("Standard library not found at %s", self.PYTHON_PATH)

        # if the dependencies are already cached from a previous session, go ahead and index them, otherwise just
        # create the folder and let them be fetched on-demand
        if os.path.exists(self.PACKAGES_PATH):
            self.index_external_modules()
        else:
            os.makedirs(self.PACKAGES_PATH)

    def cleanup(self):
        log.info("Removing package cache %s", self.PACKAGES_PATH)
        shutil.rmtree(self.PACKAGES_PATH, True)

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
        parent, this = os.path.split(library_path)
        basename, extension = os.path.splitext(this)
        if Workspace.is_package(library_path) or extension == ".py" and this != "__init__.py":
            qualified_name = ".".join((breadcrumb, basename)) if breadcrumb else basename
        elif extension == ".so":
            basename = basename.split(".")[0]
            qualified_name = ".".join((breadcrumb, basename)) if breadcrumb else basename
        else:
            qualified_name = breadcrumb

        if os.path.isdir(library_path):
            # recursively index this folder
            for child in os.listdir(library_path):
                self.index_dependencies(index, os.path.join(library_path, child), is_stdlib, qualified_name)
        elif this == "__init__.py":
            # we're already inside a package
            module_name = os.path.basename(parent)
            the_module = Module(module_name,
                                qualified_name,
                                library_path,
                                True,
                                True,
                                is_stdlib)
            index[qualified_name] = the_module
            self.module_paths[os.path.abspath(the_module.path)] = the_module
            self.fetched.add(module_name)
        elif extension == ".py":
            # just a regular non-package module
            the_module = Module(basename,
                                qualified_name,
                                library_path,
                                False,
                                True,
                                is_stdlib)
            index[qualified_name] = the_module
            self.module_paths[os.path.abspath(the_module.path)] = the_module
            self.fetched.add(basename)
        elif extension == ".so":
            # native module -- mark it as such and report a warning or something
            the_module = Module(basename,
                                qualified_name,
                                "",
                                False,
                                True,
                                is_stdlib,
                                True)
            index[qualified_name] = the_module
            self.module_paths[os.path.abspath(the_module.path)] = the_module
            self.fetched.add(basename)

    def index_project(self):
        """
        This method traverses all the project files (starting with self.PROJECT_ROOT) and indexes all the packages and
        modules contained therein. It constructs a mapping from the fully qualified module name to a Module object
        containing the metadata that Jedi needs. Because it only has a flat list of paths/uris to work with (as
        opposed to being able to walk the file tree top-down), it does some extra work to figure out the qualified
        names of each module.
        """
        all_paths = list(self.fs.walk(self.PROJECT_ROOT))

        # TODO: maybe try to exec setup.py with a sandboxed global env and builtins dict or something
        # pre-compute the set of all packages in this project -- this will be useful when trying to figure out each
        # module's qualified name, as well as the packages that are exported by this project
        package_paths = {}
        top_level_modules = set()
        for path in all_paths:
            folder, filename = os.path.split(path)
            if filename == "__init__.py":
                package_paths[folder] = True
            if folder == "/"\
                    and filename.endswith(".py")\
                    and filename not in {"__init__.py", "setup.py", "tests.py", "test.py"}:
                basename, extension = os.path.splitext(filename)
                top_level_modules.add(basename)

        # figure out this project's exports (for xpackages)
        for path in package_paths:
            if path.startswith("/"):
                path = path[1:]
            else:
                continue
            path_components = path.split("/")
            if len(path_components) > 1:
                continue
            else:
                self.project_packages.add(path_components[0])

        if not self.project_packages:  # if this is the case, then the exports must be in top-level Python files
            for m in top_level_modules:
                self.project_packages.add(m)

        # now index all modules and packages, taking care to compute their qualified names correctly (can be tricky
        # depending on how the folders are nested, and whether they have '__init__.py's or not
        for path in all_paths:
            folder, filename = os.path.split(path)
            basename, ext = os.path.splitext(filename)
            if filename == "__init__.py":
                parent, this = os.path.split(folder)
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
        package_name = qualified_name.split(".")[0]
        if package_name not in self.fetched:
            self.indexing_lock.acquire()
            self.fetched.add(package_name)
            fetch_dependency(package_name, self.PACKAGES_PATH)
            self.index_external_modules()
            self.indexing_lock.release()
        the_module = self.dependencies.get(qualified_name, None)
        if the_module and the_module.is_native:
            raise NotImplementedError("Unable to analyze native modules")
        else:
            return the_module

    def index_external_modules(self):
        for path in os.listdir(self.PACKAGES_PATH):
            if path not in self.indexed_folders:
                self.index_dependencies(self.dependencies, os.path.join(self.PACKAGES_PATH, path))
                self.indexed_folders.add(path)

    def open_module_file(self, the_module: Module, parent_span: opentracing.Span):
        if the_module.path not in self.source_paths:
            return None
        elif the_module.is_external:
            return DummyFile(self.local_fs.open(the_module.path, parent_span))
        else:
            return DummyFile(self.fs.open(the_module.path, parent_span))

    def get_module_by_path(self, path: str) -> Module:
        return self.module_paths.get(path, None)

    def get_modules(self, qualified_name: str) -> List[Module]:
        project_module = self.project.get(qualified_name, None)
        external_module = self.find_external_module(qualified_name)
        stdlib_module = self.stdlib.get(qualified_name, None)
        return list(filter(None, [project_module, external_module, stdlib_module]))

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
        if self.is_stdlib:
            return [{
                "package": {"name": "cpython"},
                "dependencies": []
            }]
        else:
            return [
                {
                    "package": {"name": p},
                    # multiple packages in the project share the same dependencies
                    "dependencies": self.get_dependencies(parent_span)
                } for p in self.project_packages
            ]

    # finds a project module using the newer, more dynamic import rules detailed in PEP 420
    # (see https://www.python.org/dev/peps/pep-0420/)
    def find_internal_module(self, name: str, qualified_name: str, dirs: List[str]):
        module_paths = []
        for parent in dirs:
            if os.path.join(parent, name, "__init__.py") in self.source_paths:
                # there's a folder at this level that implements a package with the name we're looking for
                module_path = os.path.join(parent, name, "__init__.py")
                module_file = DummyFile(self.fs.open(module_path))
                return module_file, module_path, True
            elif os.path.basename(parent) == name and os.path.join(parent, "__init__.py") in self.source_paths:
                # we're already in a package with the name we're looking for
                module_path = os.path.join(parent, "__init__.py")
                module_file = DummyFile(self.fs.open(module_path))
                return module_file, module_path, True
            elif os.path.join(parent, name + ".py") in self.source_paths:
                # there's a file at this level that implements a module with the name we're looking for
                module_path = os.path.join(parent, name + ".py")
                module_file = DummyFile(self.fs.open(module_path))
                return module_file, module_path, False
            elif self.folder_exists(os.path.join(parent, name)):
                # there's a folder at this level that implements a namespace package with the name we're looking for
                module_paths.append(os.path.join(parent, name))
            elif os.path.basename(parent) == name:
                # we're already in a namespace package with the name we're looking for
                module_paths.append(parent)
        if not module_paths:
            return None, None, None
        return None, jedi._compatibility.ImplicitNSInfo(qualified_name, module_paths), False

    def folder_exists(self, name):
        for path in self.source_paths:
            if os.path.commonpath((name, path)) == name:
                return True
        return False

    @staticmethod
    def is_package(path: str) -> bool:
        return os.path.isdir(path) and "__init__.py" in os.listdir(path)

    @staticmethod
    def get_top_level_package_names(index: Dict[str, Module]) -> Set[str]:
        return {name.split(".")[0] for name in index}
