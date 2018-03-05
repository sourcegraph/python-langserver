from distutils.sysconfig import get_python_lib
from pathlib import Path


class GlobalConfig:

    # TODO: allow different Python stdlib versions per workspace?

    PYTHON_PATH = Path(get_python_lib(standard_lib=True)).absolute()
    PACKAGES_PARENT = Path("python-langserver-cache").absolute()
    CLONED_PROJECT_PATH = Path("python-cloned-projects-cache").absolute()
    STDLIB_REPO_URL = "git://github.com/python/cpython"
    STDLIB_SRC_PATH = Path("Lib")
