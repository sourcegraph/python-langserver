from os import path as filepath

import jedi
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

    def workspace_modules(self, path) -> List[Module]:
        '''Return a set of all python modules found within a given path.'''
        dir = self.fs.listdir(path)
        modules = []
        for e in dir:
            if e.is_dir:
                subpath = filepath.join(path, e.name)
                subdir = self.fs.listdir(subpath)
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
        path = kwargs.get("path")
        trace = False
        if 'trace' in kwargs:
            trace = True
            del kwargs['trace']

        def find_module_remote(string, dir=None, fullname=None):
            """A swap-in replacement for Jedi's find module function that uses the
            remote fs to resolve module imports."""
            if trace:
                print("find_module_remote", string, dir, fullname)
            if type(dir) is list:  # TODO(renfred): handle list input for paths.
                dir = dir[0]
            dir = dir or filepath.dirname(path)
            modules = self.workspace_modules(dir)
            for m in modules:
                if m.name == string:
                    c = self.fs.open(m.path)
                    is_package = m.is_package
                    module_file = DummyFile(c)
                    module_path = filepath.dirname(
                        m.path) if is_package else m.path
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
            if trace:
                print("load_source", path)
            return self.fs.open(path)

        # TODO(keegan) It shouldn't matter if we are using a remote fs or not. Consider other ways to hook into the import system.
        if isinstance(self.fs, RemoteFileSystem):
            kwargs.update(
                find_module=find_module_remote,
                list_modules=list_modules,
                load_source=load_source, )
        return jedi.api.Script(*args, **kwargs)
