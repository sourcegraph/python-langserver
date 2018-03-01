import logging
import os
import os.path
from .config import GlobalConfig
from .fs import FileSystem
from shutil import rmtree

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

    def clone_project(self):
        """
        Clones the project from the provided filesystem into the local
        cache
        """
        all_files = self.fs.walk(self.PROJECT_ROOT)
        for file_path, file_contents in self.fs.batch_open(all_files, parent_span=None):
            # strip the leading '/' so that we can join it properly
            file_path = os.path.relpath(file_path, "/")

            cache_file_path = os.path.join(self.CLONED_PROJECT_PATH, file_path)

            os.makedirs(os.path.dirname(cache_file_path), exist_ok=True)

            with open(cache_file_path, "w") as f:
                f.write(file_contents)

    def cleanup(self):
        log.info("Removing cloned project cache %s", self.CLONED_PROJECT_PATH)
        rmtree(self.CLONED_PROJECT_PATH, ignore_errors=True)
