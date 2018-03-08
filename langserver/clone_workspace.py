import logging
from .config import GlobalConfig
from .fs import FileSystem
from shutil import rmtree
import delegator
from functools import lru_cache
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)


class CloneWorkspace:

    def __init__(self, fs: FileSystem, project_root: str,
                 original_root_path: str= ""):

        self.fs = fs
        self.PROJECT_ROOT = Path(project_root)
        self.repo = None
        self.hash = None

        if original_root_path.startswith(
                "git://") and "?" in original_root_path:
            repo_and_hash = original_root_path.split("?")
            self.repo = repo_and_hash[0]
            original_root_path = self.repo
            self.hash = repo_and_hash[1]

        if original_root_path.startswith("git://"):
            original_root_path = original_root_path[6:]

        # turn the original root path into something that can be used as a
        # file/path name or cache key
        self.key = original_root_path.replace("/", ".").replace("\\", ".")
        if self.hash:
            self.key = ".".join((self.key, self.hash))

        self.CLONED_PROJECT_PATH = GlobalConfig.CLONED_PROJECT_PATH / self.key

        log.debug("Setting Cloned Project path to %s",
                  self.CLONED_PROJECT_PATH)

        # Clone the project from the provided filesystem into the local
        # cache
        existing_pipfile = False
        for file_path in self.fs.walk(str(self.PROJECT_ROOT)):
            if file_path.endswith("Pipfile"):
                existing_pipfile = True

            cache_file_path = self.project_to_cache_path(file_path)

            cache_file_path.parent.mkdir(parents=True, exist_ok=True)
            file_contents = self.fs.open(file_path)
            cache_file_path.write_text(file_contents)

        # Install 3rd party deps

        # pipenv creates the Pipfile automatically whenever it does anything -
        # only install if the project had one to begin with
        if existing_pipfile:
            self._install_pipenv()

        self._install_pip()
        self._install_setup_py()

    def get_module_info(self, raw_jedi_module_path):
        """
        Given an absolute module path provided from jedi,
        returns a tuple of (module_kind, rel_path) where:

        module_kind: The category that the module belongs to
        (module is declared inside the project, module is a std_lib module, etc.)

        rel_path: The path of the module relative to the context
        which it's defined in. e.x: if module_kind == 'PROJECT',
        rel_path is the path of the module relative to the project's root.
        """

        module_path = Path(raw_jedi_module_path)

        if self.CLONED_PROJECT_PATH in module_path.parents:
            return (ModuleKind.PROJECT, module_path.relative_to(self.CLONED_PROJECT_PATH))

        if GlobalConfig.PYTHON_PATH in module_path.parents:
            return (ModuleKind.STANDARD_LIBRARY, module_path.relative_to(GlobalConfig.PYTHON_PATH))

        venv_path = self.VENV_PATH / "lib"
        if venv_path in module_path.parents:
            # The python libraries in a venv are stored under
            # VENV_LOCATION/lib/(some_python_version)

            python_version = module_path.relative_to(venv_path).parts[0]

            venv_lib_path = venv_path / python_version
            ext_dep_path = venv_lib_path / "site-packages"

            if ext_dep_path in module_path.parents:
                return (ModuleKind.EXTERNAL_DEPENDENCY, module_path.relative_to(ext_dep_path))

            return (ModuleKind.STANDARD_LIBRARY, module_path.relative_to(venv_lib_path))

        return (ModuleKind.UNKNOWN, module_path)

    def project_to_cache_path(self, project_path):
        """
        Translates a path from the root of the project to the equivalent path in
        the local cache.

        e.x.: '/a/b.py' -> '/python-cloned-projects-cache/project_name/a/b.py'
        """

        # strip the leading '/' so that we can join it properly
        return self.CLONED_PROJECT_PATH / project_path.lstrip("/")

    def _install_pipenv(self):
        if (self.CLONED_PROJECT_PATH / "Pipfile").exists():
            self.run_command("pipenv install -dev")

    def _install_pip(self):
        for requirements_file in self.CLONED_PROJECT_PATH.glob("*requirements.txt"):
            self.run_command(
                "pip install -r {}".format(requirements_file.absolute()))

    def _install_setup_py(self):
        if (self.CLONED_PROJECT_PATH / "setup.py").exists():
            self.run_command("python setup.py install")

    @property
    @lru_cache()
    def VENV_PATH(self):
        """
        The absolute path of the virtual environment created for this workspace.
        """
        self.ensure_venv_created()
        venv_path = self.run_command("pipenv --venv").out.rstrip()
        return Path(venv_path)

    def cleanup(self):
        log.info("Removing project's virtual environment %s", self.VENV_PATH)
        self.remove_venv()

        log.info("Removing cloned project cache %s", self.CLONED_PROJECT_PATH)
        rmtree(self.CLONED_PROJECT_PATH, ignore_errors=True)

    def ensure_venv_created(self):
        '''
        This runs a noop pipenv command, which will
        create the venv if it doesn't exist as a side effect.
        '''
        self.run_command("true")

    def remove_venv(self):
        self.run_command("pipenv --rm", no_prefix=True)

    def run_command(self, command, no_prefix=False, **kwargs):
        '''
        Runs the given command inside the context
        of the project:

        Context means:
            - the command's cwd is the cached project directory
            - the projects virtual environment is loaded into
            the command's environment
        '''
        kwargs["cwd"] = self.CLONED_PROJECT_PATH

        # add pipenv prefix
        if not no_prefix:
            if type(command) is str:
                command = "pipenv run {}".format(command)
            else:
                command = ["pipenv", "run"].append(command)

        return delegator.run(command, **kwargs)


class ModuleKind(Enum):
    PROJECT = 1
    STANDARD_LIBRARY = 2
    EXTERNAL_DEPENDENCY = 3
    UNKNOWN = 4
