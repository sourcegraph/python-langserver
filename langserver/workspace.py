from .fs import FileSystem, LocalFileSystem
from typing import Dict, Set
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


class Workspace:

    def __init__(self, fs: FileSystem, project_root: str):

        self.PROJECT_ROOT = project_root

        # TODO: THESE ARE HERE FOR EXPERIMENTAL PURPOSES; WE SHOULD PROVIDE CORRECT VALUES FOR EACH WORKSPACE ON INIT
        self.PYTHON_ROOT = "/usr/lib/python3.5"  # point to a Python installation of whatever version the project wants
        # self.PACKAGES_ROOT = "/usr/local/lib/python3.5/dist-packages"  # point to a workspace-specific packages folder
        self.PACKAGES_ROOT = "/tmp/python-dist/lib/python3.5/site-packages"

        self.fs = fs
        self.local_fs = LocalFileSystem()
        self.project = {}
        self.stdlib = {}
        self.dependencies = {}
        self.exports = None
        self.module_paths = {}

        # TODO: consider indexing modules in a separate process and setting a semaphore or something
        self.index_project()
        self.index_dependencies(self.stdlib, self.PYTHON_ROOT, True)
        self.index_dependencies(self.dependencies, self.PACKAGES_ROOT)
        self.index_exports()

        for k, v in self.dependencies.items():
            print("**** DEPENDENCY PATH:", v.path)

        print("****")

        for p in self.module_paths:
            print("**** REVERSE-MAPPED MODULE PATH:", p)

        print("****")

        for p in self.exports:
            print("**** EXPORT:", p)

        print("****")

        for p in Workspace.get_top_level_package_names(self.exports):
            print("**** TOP LEVEL PROJECT EXPORTS:", p)

        print("****")

        for p in self.get_dependencies():
            print("**** TOP LEVEL DEPENDENCY:", p)

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
                continue

            if filename == "__init__.py":
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
                continue

            if extension != ".py" or basename.startswith("__") and basename.endswith("__"):
                # not a relevant file
                continue

            if extension == ".py":
                # just a regular non-package module
                the_module = Module(basename,
                                    qualified_name,
                                    os.path.join(library_path, filename),
                                    False,
                                    True,
                                    is_stdlib)
                index[qualified_name] = the_module
                self.module_paths[the_module.path] = the_module
                continue

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

    def index_exports(self):
        """
        This method compares the packages and modules in the project against the ones that are installed through the
        dependencies, in order to determine which project modules are exported. This works because running a project's
        setup script also installs the project itself in the dist-packages/site-packages folder. We need to determine
        the exported modules in order to provide symbol descriptors for cross-repository operations.
        """
        # TODO: try to get exports from a more reliable place ... maybe hook into setup.py or something
        project_things = set(self.project.keys())
        library_things = set(self.dependencies.keys())
        exported_things = project_things.intersection(library_things)
        self.exports = exported_things

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

    def get_dependencies(self) -> Set[str]:
        top_level_external_packages = Workspace.get_top_level_package_names(self.dependencies)
        top_level_project_exports = Workspace.get_top_level_package_names(self.exports)
        return top_level_external_packages.difference(top_level_project_exports)

    @staticmethod
    def get_top_level_package_names(index: Dict[str, Module]) -> Set[str]:
        return {name.split(".")[0] for name in index}
