import tempfile
import subprocess
import os
import shutil
import logging

import pip
import pip.status_codes

from requirements import parse

log = logging.getLogger(__name__)


def fetch_dependency(module_name: str, specifier: str, install_path: str):
    """
    Shells out to PIP in order to download and unzip the named package into the specified path. This method only runs
    `pip download`, NOT `pip install`, so it's presumably safe.
    :param module_name: the name of the package to download
    :param specifier: the version specifier for the package
    :param install_path: the path in which to install the downloaded package
    """
    with tempfile.TemporaryDirectory() as download_folder:
        log.info("Attempting to download package %s to %s", module_name, download_folder, exc_info=True)
        # TODO: check the result status

        index_url = os.environ.get('INDEX_URL')
        if index_url is not None:
            result = pip.main(["download", "--no-deps", "-i", index_url, "-d", download_folder, module_name+specifier])
        else:
            result = pip.main(["download", "--no-deps", "-d", download_folder, module_name+specifier])
        if result != pip.status_codes.SUCCESS:
            log.error("Unable to fetch package %s", module_name)
            return
        for thing in os.listdir(download_folder):
            thing_abs = os.path.join(download_folder, thing)
            if os.path.isdir(thing_abs):
                log.debug("Moving %s to %s", thing, install_path, exc_info=True)
                shutil.move(thing_abs, install_path)
            elif thing.endswith(".whl") or thing.endswith(".zip"):
                log.debug("Unzipping %s to %s", thing, install_path, exc_info=True)
                result = subprocess.run(["unzip", "-o", "-d", install_path, thing_abs])
            elif thing.endswith(".tar.gz"):
                log.debug("Untarring %s to %s", thing, install_path, exc_info=True)
                result = subprocess.run(["tar", "-C", install_path, "-xzf", thing_abs])
            elif thing.endswith(".tar.bz2"):
                log.debug("Untarring %s to %s", thing, install_path, exc_info=True)
                result = subprocess.run(["tar", "-C", install_path, "-xjf", thing_abs])
            else:
                log.warning("Unrecognized package file: %s", thing, exc_info=True)

def parse_requirements(req_path, file_system):
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
    req_string = file_system.open(req_path)
    requirements = parse(req_string, current_path = req_path, file_system = file_system)
    return { req.name:req.specs for req in requirements if req.specifier}

def get_specifier_for_requirement(requirement, requirements_map):
    """
    Returns the specifier string to use for a given requirement. 
    """
    specifier_strs = []
    for spec in requirements_map.get(requirement, [""]):
        specifier_strs.append("".join(spec))
    
    return ",".join(specifier_strs)
