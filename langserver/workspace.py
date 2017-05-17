from .fs import FileSystem, LocalFileSystem
from typing import Dict
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
    def __init__(self, name, path, is_package=False, qualified_name=None, is_external=False):
        self.name = name
        if qualified_name:
            self.qualified_name = qualified_name
        else:
            self.qualified_name = name
        self.path = path
        self.is_package = is_package
        self.is_external = is_external

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

        # TODO: consider indexing modules in a separate process and setting a semaphore or something
        self.index_project()
        self.index_dependencies(self.stdlib, self.PYTHON_ROOT)
        self.index_dependencies(self.dependencies, self.PACKAGES_ROOT)
        self.index_exported_packages()

        for p in self.exports:
            print("EXPORTED MODULE:", p)

    def index_dependencies(self, index: Dict[str, Module], library_path: str, breadcrumb: str=None):
        """
        Given a root library path (e.g., the Python root path or the dist-packages root path), this method traverses
        it recursively and indexes all the packages and modules contained therein. It constructs a mapping from the
        fully qualified module name to a Module object containing the metadata that Jedi needs.

        :param index: the dictionary that should be used to store this index (will be modified)
        :param library_path: the root path containing the modules and packages to be indexed
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
                self.index_dependencies(index, os.path.join(library_path, filename), qualified_name)
                continue

            if filename == "__init__.py":
                # we're already inside a package
                module_name = os.path.basename(library_path)
                the_module = Module(module_name, os.path.join(library_path, filename), True, qualified_name, True)
                index[qualified_name] = the_module
                continue

            if extension != ".py" or basename.startswith("__") and basename.endswith("__"):
                # not a relevant file
                continue

            if extension == ".py":
                # just a regular non-package module
                the_module = Module(basename, os.path.join(library_path, filename), False, qualified_name, True)
                index[qualified_name] = the_module
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
                the_module = Module(module_name, path, True, qualified_name)
                self.project[qualified_name] = the_module
            elif ext == ".py" and not basename.startswith("__") and not basename.endswith("__"):
                the_module = Module(basename, path, False, qualified_name)
                self.project[qualified_name] = the_module

    def index_exported_packages(self):
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
