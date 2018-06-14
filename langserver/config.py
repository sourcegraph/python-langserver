import distutils
import tempfile


class GlobalConfig:

    # TODO: allow different Python stdlib versions per workspace?

    PYTHON_PATH = distutils.sysconfig.get_python_lib(standard_lib=True)
    PACKAGES_PARENT = tempfile.mkdtemp(
        prefix="python-langserver-cache")
    STDLIB_REPO_URL = "git://github.com/python/cpython"
    STDLIB_SRC_PATH = "Lib"
