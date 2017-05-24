class GlobalConfig:
    # TODO: allow different Python stdlib versions
    PYTHON_PATH = "/usr/local/lib/python3.6"  # OVERRIDE THIS ON THE COMMAND LINE IF NECESSARY
    PACKAGES_PARENT = "python-langserver-cache"
    STDLIB_REPO_URL = "git://github.com/python/cpython"
    STDLIB_SRC_PATH = "Lib"
    # whitelist of native modules that are safe to load and initialize so that we can provide some intelligence
    NATIVE_WHITELIST = {
        "numpy"
    }
