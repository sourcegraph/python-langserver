import tempfile
import subprocess
import os
import shutil


def fetch_dependency(module_name: str, install_path: str):
    """
    Shells out to PIP in order to download and unzip the named package into the specified path. This method only runs
    `pip download`, NOT `pip install`, so it's presumably safe.
    :param module_name: the name of the package to download
    :param install_path: the path in which to install the downloaded package
    """
    with tempfile.TemporaryDirectory() as download_folder:
        print("**** DOWNLOADING PACKAGE", module_name, "TO", install_path)
        # TODO: check the result status
        result = subprocess.run(["pip3", "download", "-d", download_folder, module_name])
        for thing in os.listdir(download_folder):
            thing_abs = os.path.join(download_folder, thing)
            if os.path.isdir(thing_abs):
                shutil.move(thing_abs, install_path)
            elif thing.endswith(".whl") or thing.endswith(".zip"):
                result = subprocess.run(["unzip", "-o", "-d", install_path, thing_abs])
            elif thing.endswith(".tar.gz"):
                result = subprocess.run(["tar", "-C", install_path, "-xzf", thing_abs])
            else:
                print("**** UNRECOGNIZED PACKAGE FILE:", thing)
