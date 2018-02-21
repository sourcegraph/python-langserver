import tempfile
import subprocess
import os
import shutil
import logging
import six
from .package_configuation import Source
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import pip
import pip.status_codes

log = logging.getLogger(__name__)


def fetch_dependency(module_name: str, install_path: str, configured_deps: dict, configured_sources: dict):
    """
    Shells out to PIP in order to download and unzip the named package into the specified path. This method only runs
    `pip download`, NOT `pip install`, so it's presumably safe.
    :param module_name: the name of the package to download
    :param install_path: the path in which to install the downloaded package
    """
    with tempfile.TemporaryDirectory() as download_folder:
        log.info("Attempting to download package %s to %s", module_name, download_folder, exc_info=True)
        index_url = os.environ.get('INDEX_URL') or 'https://pypi.python.org/simple'
        source = Source("pypi", "https://pypi.python.org/simple", True)
        # TODO: check the result status
        if module_name in configured_deps:
            dep = configured_deps[module_name]
            print("$$$$$$$$$$$$$$$")
            print('#### name', dep.name)
            print('#### version', dep.version)
            print('#### index name', dep.index_name)
            print('### URL', configured_sources['name'].url)
            print("$$$$$$$$$$$$$$$")
            if dep.index_name in configured_sources:
                index_url = configured_sources[dep.index_name].url
                source.name = configured_sources[dep.index_name]

            args = convert_deps_to_pip(configured_deps[module_name], source, include_index=True)[0]
            if index_url is not None:
                result = pip.main(["download", "--no-deps", "-d", download_folder, args])
            else:
                result = pip.main(["download", "--no-deps", "-d", download_folder, args])
        else:
            if index_url is not None:
                result = pip.main(["download", "--no-deps", "-i", index_url, "-d", download_folder, module_name])
            else:
                result = pip.main(["download", "--no-deps", "-d", download_folder, module_name])

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

def prepare_pip_source_args(source, pip_args=None):
    if pip_args is None:
        pip_args = []

    if source:
        # Add the source to pip.
        pip_args.extend(['-i', source.url])

        # Trust the host if it's not verified.
        if not source.verify_ssl==True:
            pip_args.extend(['--trusted-host', urlparse(source.url).netloc.split(':')[0]])
    return pip_args


def convert_deps_to_pip(dep, source, include_index=False):
    """"Converts a Pipfile-formatted dependency to a pip-formatted one."""
    dependencies = []
    # Default (e.g. '>1.10').
    version = ''
    index = ''

    hash = ''
    # Support for single hash (spec 1).

    if not dep.version == '*':
        version = dep.version

    if include_index:
        # get source url
        pip_args = prepare_pip_source_args(source)
        index = ' '.join(pip_args)

    version = '{0}{1}'.format(dep.name, version).strip()
    ### final format is pip download --no-deps 'eventlet==0.16.0' -i https://pypi.com
    dependencies.append(version)
    dependencies.append(index)
    return dependencies
