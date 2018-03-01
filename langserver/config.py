import distutils


class GlobalConfig:

    # TODO: allow different Python stdlib versions per workspace?

    PYTHON_PATH = distutils.sysconfig.get_python_lib(standard_lib=True)
    PACKAGES_PARENT = "python-langserver-cache"
    CLONED_PROJECT_PATH = "python-cloned-projects-cache"
    STDLIB_REPO_URL = "git://github.com/python/cpython"
    STDLIB_SRC_PATH = "Lib"
