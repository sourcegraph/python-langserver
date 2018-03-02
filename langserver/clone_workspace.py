import logging
import os
import os.path
from .config import GlobalConfig
from .fs import FileSystem
from shutil import rmtree
import delegator
import json

log = logging.getLogger(__name__)


class CloneWorkspace:

    def __init__(self, fs: FileSystem, project_root: str,
                 original_root_path: str= ""):

        self.PROJECT_ROOT = project_root
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

        # TODO: allow different Python versions per project/workspace
        self.PYTHON_PATH = GlobalConfig.PYTHON_PATH
        self.CLONED_PROJECT_PATH = os.path.join(
            GlobalConfig.CLONED_PROJECT_PATH, self.key)
        log.debug("Setting Python path to %s", self.PYTHON_PATH)
        log.debug("Setting Cloned Project path to %s",
                  self.CLONED_PROJECT_PATH)

        self.fs = fs

        # Clone the project from the provided filesystem into the local
        # cache
        all_files = self.fs.walk(self.PROJECT_ROOT)
        for file_path in all_files:
            cache_file_path = self.to_cache_path(file_path)
            if os.path.exists(cache_file_path):
                continue

            os.makedirs(os.path.dirname(cache_file_path), exist_ok=True)
            file_contents = self.fs.open(file_path)
            with open(cache_file_path, "w") as f:
                f.write(file_contents)

        self.ensure_venv_created()
        self.VENV_LOCATION = self.run_command("pipenv --venv").out

    def cleanup(self):
        log.info("Removing project's virtual emvironment %s", self.VENV_LOCATION)
        self.remove_venv()

        log.info("Removing cloned project cache %s", self.CLONED_PROJECT_PATH)
        rmtree(self.CLONED_PROJECT_PATH, ignore_errors=True)

    def to_cache_path(self, project_path):
        """
        Translates a path from the root of the project to the equivalent path in
        the local cache.

        e.x.: '/a/b.py' -> 'python-cloned-projects-cache/project_name/a/b.py'
        """
        # strip the leading '/' so that we can join it properly
        file_path = os.path.relpath(project_path, "/")

        return os.path.join(self.CLONED_PROJECT_PATH, file_path)

    def ensure_venv_created(self):
        '''
        This runs a noop pipenv command, which will
        create the venv if it doesn't exist as a side effect.
        '''
        self.run_command("true")

    def remove_venv(self):
        self.run_command("pipenv --rm")

    def get_package_information(self):
        project_packages = self.project_packages()
        dependencies = self.external_dependencies()

        out = []
        for package in project_packages:
            out.append({
                "package": {
                    "name": package
                },
                "dependencies": dependencies
            })
        return out

    def project_packages(self):
        '''
        Provides a list of all packages declared in the project
        '''
        script = [
            "import json",
            "import setuptools",
            "pkgs = setuptools.find_packages()",
            "print(json.dumps(pkgs))"
        ]

        c = self.run_command("python -c '{}'".format(";".join(script)))
        return json.loads(c.out)

    def external_dependencies(self):
        '''
        Provides a list of third party packages that the
        project depends on.
        '''
        deps = json.loads(self.run_command(
            "pip list --local --format json").out)
        out = [
            {
                # TODO - is this ever not a dependency?
                "attributes": {
                    "name": "cpython",
                    "repoURL": "git://github.com/python/cpython"
                }
            }
        ]

        for dep in deps:
            dep_name = dep["name"]
            if dep_name not in set(["pip", "wheel"]):
                out.append({"attributes": {"name": dep["name"]}})

        return out

    def run_command(self, command, **kwargs):
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
        if type(command) is str:
            command = "pipenv run {}".format(command)
        else:
            command = ["pipenv", "run"].append(command)

        return delegator.run(command, **kwargs)
