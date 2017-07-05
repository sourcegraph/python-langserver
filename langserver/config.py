import os
import os.path


class GlobalConfig:

    # TODO: allow different Python stdlib versions per workspace?

    PYTHON_PATH = os.path.dirname(os.__file__)
    PACKAGES_PARENT = "python-langserver-cache"
    STDLIB_REPO_URL = "git://github.com/python/cpython"
    STDLIB_SRC_PATH = "Lib"
