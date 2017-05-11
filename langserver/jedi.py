from os import path as filepath

import jedi
import opentracing
from typing import List

from .fs import RemoteFileSystem


class Module:
    def __init__(self, name, path, is_package=False):
        self.name = name
        self.path = path
        self.is_package = is_package

    def __repr__(self):
        return "PythonModule({}, {})".format(self.name, self.path)


class DummyFile:
    def __init__(self, contents):
        self.contents = contents

    def read(self):
        return self.contents

    def close(self):
        pass


class RemoteJedi:
    def __init__(self, fs, root_path):
        self.fs = fs
        self.root_path = root_path

    def workspace_modules(self, path, parent_span) -> List[Module]:
        """Return a set of all python modules found within a given path."""

        with opentracing.start_child_span(parent_span, "workspace_modules") as workspace_modules_span:
            workspace_modules_span.set_tag("path", path)

            dir = self.fs.listdir(path, workspace_modules_span)
            modules = []
            for e in dir:
                if e.is_dir:
                    subpath = filepath.join(path, e.name)
                    subdir = self.fs.listdir(subpath, workspace_modules_span)
                    if any([s.name == "__init__.py" for s in subdir]):
                        modules.append(
                            Module(e.name,
                                   filepath.join(subpath, "__init__.py"), True))
                else:
                    name, ext = filepath.splitext(e.name)
                    if ext == ".py":
                        if name == "__init__":
                            name = filepath.basename(path)
                            modules.append(
                                Module(name, filepath.join(path, e.name), True))
                        else:
                            modules.append(
                                Module(name, filepath.join(path, e.name)))

            return modules

    def new_script(self, *args, **kwargs):
        """Return an initialized Jedi API Script object."""
        if "parent_span" in kwargs:
            parent_span = kwargs.get("parent_span")
            del kwargs["parent_span"]
        else:
            parent_span = opentracing.tracer.start_span("new_script_parent")

        with opentracing.start_child_span(parent_span, "new_script") as new_script_span:
            path = kwargs.get("path")
            new_script_span.set_tag("path", path)
            return self._new_script_impl(new_script_span, *args, **kwargs)

    def _new_script_impl(self, parent_span, *args, **kwargs):
        path = kwargs.get("path")

        trace = False
        if 'trace' in kwargs:
            trace = True
            del kwargs['trace']

        def find_module_remote(string, dir=None, fullname=None):
            """A swap-in replacement for Jedi's find module function that uses the
            remote fs to resolve module imports."""
            with opentracing.start_child_span(parent_span, "find_module_remote_callback") as find_module_span:
                if trace:
                    print("find_module_remote", string, dir, fullname)
                if type(dir) is list:  # TODO(renfred): handle list input for paths.
                    dir = dir[0]
                dir = dir or filepath.dirname(path)
                modules = self.workspace_modules(dir, find_module_span)
                for m in modules:
                    if m.name == string:
                        c = self.fs.open(m.path, find_module_span)
                        is_package = m.is_package
                        module_file = DummyFile(c)
                        module_path = filepath.dirname(
                            m.path) if is_package else m.path
                        find_module_span.set_tag("module-path", module_path)
                        find_module_span.set_tag("module-file", module_file)
                        find_module_span.set_tag("is-package", is_package)
                        return module_file, module_path, is_package
                else:
                    raise ImportError('Module "{}" not found in {}', string, dir)

        def list_modules() -> List[str]:
            if trace:
                print("list_modules")
            modules = [
                f for f in self.fs.walk(self.root_path)
                if f.lower().endswith(".py")
            ]
            return modules

        def load_source(path) -> str:
            with opentracing.start_child_span(parent_span, "load_source_callback") as load_source_span:
                load_source_span.set_tag("path", path)
                if trace:
                    print("load_source", path)
                result = self.fs.open(path, load_source_span)
                return result

        # TODO(keegan) It shouldn't matter if we are using a remote fs or not. Consider other ways to hook into the import system.
        if isinstance(self.fs, RemoteFileSystem):
            kwargs.update(
                find_module=find_module_remote,
                list_modules=list_modules,
                load_source=load_source, )

        return jedi.api.Script(*args, **kwargs)
