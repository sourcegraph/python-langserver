import logging
from .config import GlobalConfig
from .fs import FileSystem, TestFileSystem
from shutil import rmtree
import delegator
from functools import lru_cache
from enum import Enum
from pathlib import Path
import os

log = logging.getLogger(__name__)


class Workspace:

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
        for file_path in self.fs.walk(str(self.PROJECT_ROOT)):

            cache_file_path = self.project_to_cache_path(file_path)
            try:
                file_contents = self.fs.open(file_path)
                cache_file_path.parent.mkdir(parents=True, exist_ok=True)
                cache_file_path.write_text(file_contents)
            except UnicodeDecodeError as e:
                if isinstance(self.fs, TestFileSystem):
                    # assume that it's trying to write some non-text file, which
                    # should only happen when running tests
                    continue
                else:
                    raise e

        self.project = Project(self.CLONED_PROJECT_PATH,
                               self.CLONED_PROJECT_PATH)

    def find_project_for_path(self, path):
        return self.project.find_project_for_path(path)

    def project_to_cache_path(self, project_path):
        """
        Translates a path from the root of the project to the equivalent path in
        the local cache.

        e.x.: '/a/b.py' -> '/python-cloned-projects-cache/project_name/a/b.py'
        """

        # strip the leading '/' so that we can join it properly
        return self.CLONED_PROJECT_PATH / project_path.lstrip("/")

    def cleanup(self):
        self.project.cleanup()


class Project:
    def __init__(self, workspace_root_dir, project_root_dir):
        self.WORKSPACE_ROOT_DIR = workspace_root_dir
        self.PROJECT_ROOT_DIR = project_root_dir
        self.sub_projects = self._find_subprojects(project_root_dir)
        self._install_external_dependencies()

    def _find_subprojects(self, current_dir):
        '''
        Returns a map containing the top-level subprojects contained inside
        this project, keyed by the absolute path to the subproject.
        '''
        sub_projects = {}

        top_level_folders = (
            child for child in current_dir.iterdir() if child.is_dir())

        for folder in top_level_folders:

            def gen_len(generator):
                return sum(1 for _ in generator)

            # do any subfolders contain installation files?
            if any(gen_len(folder.glob(pattern)) for pattern in INSTALLATION_FILE_PATTERNS):
                sub_projects[folder] = Project(self.WORKSPACE_ROOT_DIR, folder)
            else:
                sub_projects.update(self._find_subprojects(folder))

        return sub_projects

    def find_project_for_path(self, path):
        '''
        Returns the deepest project instance that contains this path.

        '''
        if path.is_file():
            folder = path.parent
        else:
            folder = path

        if folder == self.PROJECT_ROOT_DIR:
            return self

        # If the project_dir isn't an ancestor of the folder,
        # there is no way it or any of its subprojects
        # could contain this path
        if self.PROJECT_ROOT_DIR not in folder.parents:
            return None

        for sub_project in self.sub_projects.values():
            deepest_project = sub_project.find_project_for_path(path)
            if deepest_project is not None:
                return deepest_project

        return self

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

        if self.PROJECT_ROOT_DIR in module_path.parents:
            return (ModuleKind.PROJECT, module_path.relative_to(self.WORKSPACE_ROOT_DIR))

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

    def _install_external_dependencies(self):
        """
        Installs the external dependencies for the project.

        Known limitations:
        - doesn't handle installation files that aren't in the root of the workspace
        - no error handling if any of the installation steps will prompt the user for whatever
        reason
        """
        self._install_setup_py()
        self._install_pip()
        self._install_pipenv()

    def _install_pipenv(self):
        if (self.PROJECT_ROOT_DIR / "Pipfile.lock").exists():
            self.run_command("pipenv install --dev --ignore-pipfile")
        elif (self.PROJECT_ROOT_DIR / "Pipfile").exists():
            self.run_command("pipenv install --dev")

    def _install_pip(self):
        for requirements_file in self.PROJECT_ROOT_DIR.glob(REQUIREMENTS_GLOB_PATTERN):
            self.run_command(
                "pip install -r {}".format(str(requirements_file.absolute())))

    def _install_setup_py(self):
        if (self.PROJECT_ROOT_DIR / "setup.py").exists():
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
        for sub_project in self.sub_projects.values():
            sub_project.cleanup()

        log.info("Removing project's virtual environment %s", self.VENV_PATH)
        self.remove_venv()

        log.info("Removing cloned project cache %s", self.PROJECT_ROOT_DIR)
        rmtree(self.PROJECT_ROOT_DIR, ignore_errors=True)

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
        kwargs["cwd"] = self.PROJECT_ROOT_DIR

        if not no_prefix:

            # HACK: this is to get our spawned pipenv to keep creating
            # venvs even if the language server itself is running inside one
            # See:
            # https://github.com/pypa/pipenv/blob/4e8deda9cbf2a658ab40ca31cc6e249c0b53d6f4/pipenv/environments.py#L58

            env = kwargs.get("env", os.environ.copy())
            env["VIRTUAL_ENV"] = ""
            kwargs["env"] = env

            if type(command) is str:
                command = "pipenv run {}".format(command)
            else:
                command = ["pipenv", "run"].append(command)

        return delegator.run(command, **kwargs)


REQUIREMENTS_GLOB_PATTERN = "*requirements.txt"

INSTALLATION_FILE_PATTERNS = ["Pipfile", REQUIREMENTS_GLOB_PATTERN, "setup.py"]


class ModuleKind(Enum):
    PROJECT = 1
    STANDARD_LIBRARY = 2
    EXTERNAL_DEPENDENCY = 3
    UNKNOWN = 4
