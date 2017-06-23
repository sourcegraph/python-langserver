from os import path as filepath
import os

import jedi
import jedi._compatibility

import opentracing
from typing import List

from .fs import RemoteFileSystem, TestFileSystem


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
    def __init__(self, fs, workspace, root_path):
        self.fs = fs
        self.workspace = workspace
        self.root_path = root_path

    def new_script(self, *args, **kwargs):
        """Return an initialized Jedi API Script object."""
        if "parent_span" in kwargs:
            parent_span = kwargs.get("parent_span")
            del kwargs["parent_span"]
        else:
            parent_span = opentracing.tracer.start_span("new_script_parent")

        with opentracing.start_child_span(parent_span,
                                          "new_script") as new_script_span:
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
            if dir is None:
                # If we're starting the search for a module, then proceed from both the project root as well as the
                # folder containing the current file. Normally we should only search from the project root (I think),
                # but certain repos such as collections of example projects are structured such that we can support
                # them better by searching relative to the current file, too.
                dir = ["/", os.path.dirname(path)]
            with opentracing.start_child_span(
                    parent_span,
                    "find_module_remote_callback") as find_module_span:
                if trace:
                    print("find_module_remote", string, dir, fullname)

                the_module = None

                # TODO: move this bit of logic into the Workspace?
                # default behavior is to search for built-ins first, but skip this if we're actually in the stdlib repo
                if fullname and not self.workspace.is_stdlib:
                    the_module = self.workspace.find_stdlib_module(fullname)

                if the_module == "native":  # break if we get a native module
                    raise ImportError('Module "{}" not found in {}', string, dir)

                # TODO: use this clause's logic for the other clauses too (stdlib and external modules)
                # after searching for built-ins, search the current project
                if not the_module:
                    module_file, module_path, is_package = self.workspace.find_internal_module(string, fullname, dir)
                    if module_file or module_path:
                        if is_package and module_path.endswith(".py"):
                            module_path = os.path.dirname(module_path)
                        return module_file, module_path, is_package

                # finally, search 3rd party dependencies
                if not the_module:
                    the_module = self.workspace.find_external_module(fullname)

                if not the_module:
                    raise ImportError('Module "{}" not found in {}', string, dir)

                is_package = the_module.is_package
                module_file = self.workspace.open_module_file(the_module, find_module_span)
                module_path = the_module.path
                if is_package and the_module.is_namespace_package:
                    module_path = jedi._compatibility.ImplicitNSInfo(fullname, [module_path])
                    is_package = False
                elif is_package and module_path.endswith(".py"):
                    module_path = filepath.dirname(module_path)
                return module_file, module_path, is_package

        # TODO: update this to use the workspace's module indices
        def list_modules() -> List[str]:
            if trace:
                print("list_modules")
            modules = [
                f for f in self.fs.walk(self.root_path)
                if f.lower().endswith(".py")
            ]
            return modules

        def load_source(path) -> str:
            with opentracing.start_child_span(
                    parent_span, "load_source_callback") as load_source_span:
                load_source_span.set_tag("path", path)
                if trace:
                    print("load_source", path)
                result = self.fs.open(path, load_source_span)
                return result

        # TODO(keegan) It shouldn't matter if we are using a remote fs or not. Consider other ways to hook into the import system.
        # TODO(aaron) Also, it shouldn't matter whether we're using a "real" filesystem or our test harness filesystem
        if isinstance(self.fs, RemoteFileSystem) or isinstance(self.fs, TestFileSystem):
            kwargs.update(
                find_module=find_module_remote,
                list_modules=list_modules,
                load_source=load_source,
                fs=self.fs
            )

        return jedi.api.Script(*args, **kwargs)
