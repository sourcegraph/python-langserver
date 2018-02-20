import tempfile
import subprocess
import os
import shutil
import logging
import six
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import pip
import pip.status_codes

log = logging.getLogger(__name__)


def fetch_dependency(module_name: str, install_path: str, configured_deps: dict):
    """
    Shells out to PIP in order to download and unzip the named package into the specified path. This method only runs
    `pip download`, NOT `pip install`, so it's presumably safe.
    :param module_name: the name of the package to download
    :param install_path: the path in which to install the downloaded package
    """
    with tempfile.TemporaryDirectory() as download_folder:
        log.info("Attempting to download package %s to %s", module_name, download_folder, exc_info=True)
        index_url = os.environ.get('INDEX_URL')
        # TODO: check the result status
        if module_name in configured_deps:
            dep = configured_deps[module_name]
            index_url = dep['source']['url'] or os.environ.get('INDEX_URL')
            args = convert_deps_to_pip(configured_deps[module_name], include_index=True)[0]
            print('### ARGS', args)
            if index_url is not None:
                result = pip.main(["download", "--no-deps", "-d", download_folder, args])
                print('### RESULT', result)
            else:
                result = pip.main(["download", "--no-deps", "-d", download_folder, args])
                print('### RESULTELSE', result)
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

def prepare_pip_source_args(sources, pip_args=None):
    print('### PIP ARGS ', pip_args)
    print('### SOURCES ', sources)
    if pip_args is None:
        pip_args = []

    if sources:
        # Add the source to pip.
        pip_args.extend(['-i', sources[0]['url']])

        print('###sources get ssl', sources[0].get('verify_ssl', True))
        # Trust the host if it's not verified.
        if not sources[0].get('verify_ssl', True):
            pip_args.extend(['--trusted-host', urlparse(sources[0]['url']).netloc.split(':')[0]])

        # Add additional sources as extra indexes.
        if len(sources) > 1:
            for source in sources[1:]:
                pip_args.extend(['--extra-index-url', source['url']])

                # Trust the host if it's not verified.
                if not source.get('verify_ssl', True):
                    pip_args.extend(['--trusted-host', urlparse(source['url']).netloc.split(':')[0]])
    print('### returned pip args', pip_args)
    return pip_args


def convert_deps_to_pip(dep, include_index=False):
    """"Converts a Pipfile-formatted dependency to a pip-formatted one."""
    dependencies = []
    # Default (e.g. '>1.10').
    version = ''
    index = ''

    hash = ''
    # Support for single hash (spec 1).
    if 'hash' in dep:
        hash = ' --hash={0}'.format(dep['hash'])

    # Support for multiple hashes (spec 2).
    if 'hashes' in dep:
        hash = '{0} '.format(''.join([' --hash={0} '.format(h) for h in dep['hashes']]))

    # Support for extras (e.g. requests[socks])
    if 'extras' in dep:
        extra = '[{0}]'.format(dep['extras'][0])

    if 'version' in dep:
        if not dep['version'] == '*':
            version = dep['version']

    if include_index:
        if dep['source']:
            # get source url
            pip_args = prepare_pip_source_args([dep['source']])
            index = ' '.join(pip_args)

    # Support for files.
    if 'file' in dep:
        extra = '{1}{0}'.format(extra, dep['file']).strip()

        # Flag the file as editable if it is a local relative path
        if 'editable' in dep:
            dep = '-e '
        else:
            dep = ''

    # Support for paths.
    elif 'path' in dep:
        print('## DEP', dep)
        extra = '{1}{0}'.format(extra, dep['path']).strip()

        # Flag the file as editable if it is a local relative path
        if 'editable' in dep:
            dep = '-e '
        else:
            dep = ''

    version = '{0}{1}'.format(dep['package_name'], version).strip()
    dependencies.append(version)
    dependencies.append(index)
    return dependencies
