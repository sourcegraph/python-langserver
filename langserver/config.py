import os.path

class GlobalConfig:

    # TODO: allow different Python stdlib versions per workspace?

    # Check for a local python stdlib file in order to determine the folder -- we can't check for just the folder
    # because there may be python folders in the following locations that don't contain the stdlib.
    # OVERRIDE THIS ON THE COMMAND LINE IF NECESSARY
    if os.path.exists("/usr/local/lib/python3.6/os.py"):
        PYTHON_PATH = "/usr/local/lib/python3.6"
    elif os.path.exists("/usr/lib/python3.6/os.py"):
        PYTHON_PATH = "/usr/lib/python3.6"
    elif os.path.exists("/usr/local/lib/python3.5/os.py"):
        PYTHON_PATH = "/usr/local/lib/python3.5"
    elif os.path.exists("/usr/lib/python3.5/os.py"):
        PYTHON_PATH = "/usr/lib/python3.5"
    elif os.path.exists("/usr/local/lib/python/os.py"):
        PYTHON_PATH = "/usr/local/lib/python"
    else:
        PYTHON_PATH = "/usr/lib/python"

    PIP_COMMAND = "pip"  # OVERRIDE THIS ON THE COMMAND LINE IF NECESSARY
    PACKAGES_PARENT = "python-langserver-cache"
    STDLIB_REPO_URL = "git://github.com/python/cpython"
    STDLIB_SRC_PATH = "Lib"
    # whitelist of native modules that are safe to load and initialize so that we can provide some intelligence
    NATIVE_WHITELIST = {
        "numpy",
        "tensorflow"
    }
