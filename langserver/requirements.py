from .fs import FileSystem, FileException
from requirements import parse

import logging

log = logging.getLogger(__name__)


class Requirements:
    def __init__(self, fs: FileSystem, requirements_path: str):
        self.fs = fs
        self.requirements_path = requirements_path
        self.requirements_map = {}
        self.set_requirements_map()

    def set_requirements_map(self):
        req_map = {}
        try:
            self.req_map = self.parse_requirements()
        except(FileException, FileNotFoundError):
            pass

    def parse_requirements(self):
        """
        Parses the pip requirements file located at req_path. Returns a map of package names
        to their version specifiers.

        :param req_path: the path to the pip requirements file. Throws a FileNotFound or a FileException if
        req_file is not valid

        :param file_system: the file system to use to open the requirements file @ req_path and any other
        recursive calls.

        Known limitations:

        - All requirements files with that use the '--find-links', '--index-url', '--extra-index-url'
        or '--no-index' flags are ignored.

        - All requirements that don't use a requirements specifier (e.x. django>=1.5 ) are ignored.
        """
        req_path = self.requirements_path
        file_system = self.fs
        req_string = file_system.open(req_path)
        requirements = parse(req_string, current_path=req_path,
                             file_system=file_system)
        return {req.name: req.specs for req in requirements if req.specifier}

    def get_specifier_for_requirement(self, requirement):
        """
        Returns the specifier string to use for a given requirement.
        """
        specifier_strs = []
        for spec in self.requirements_map.get(requirement, [""]):
            specifier_strs.append("".join(spec))

        return ",".join(specifier_strs)
