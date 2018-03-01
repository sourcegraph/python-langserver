from requirements import parse


def parse_requirements(req_path, file_system):
    """Parses the pip requirements file located at req_path. Returns a map of
    package names to their version specifiers.

    :param req_path: the path to the pip requirements file. Throws a FileNotFound or a
    FileException if req_path is not valid

    :param file_system: the file system to use to open the requirements file @ req_path
    and any other recursive calls.

    Known limitations:

    - All requirements files with that use the '--find-links', '--index-url', '--extra-index-url'
    or '--no-index' flags are ignored.

    - All requirements that don't use a version specifier (e.x. django>=1.5 ) are ignored.
    """
    req_string = file_system.open(req_path)
    requirements = parse(req_string, current_path=req_path,
                         file_system=file_system)
    return {req.name: req.specs for req in requirements if req.specifier}


def get_version_specifier_for_pkg(pkg, pkg_specifiers_map):
    """Returns the specifier string to use for a given requirement. If pkg has
    no corresponding entry in the pkg_specifiers_map, a string representing
    that any version is allowed is returned.

    :param pkg: the name of the package to get the version specifier for
    :param pkg_specifiers_map: a map of packages to their respective version specifiers
    from a parsed requirements file
    """

    specifier_strs = []
    for spec in pkg_specifiers_map.get(pkg, [""]):
        specifier_strs.append("".join(spec))

    return ",".join(specifier_strs)
