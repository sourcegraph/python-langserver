from .harness import Harness, print_result
import uuid


flask_workspace = Harness("repos/flask")
flask_workspace.initialize("git://github.com/pallets/flask?" + str(uuid.uuid4()))


def test_x_packages():
    result = flask_workspace.x_packages()
    assert result
    result = result[0]
    assert "package" in result and result["package"] == {'name': 'flask'}
    assert "dependencies" in result
    dep_names = {d["attributes"]["name"] for d in result["dependencies"]}
    assert dep_names == {
        'blueprintapp',
        'hello',
        'minitwit',
        'werkzeug',
        'setuptools',
        'pytest',
        'itsdangerous',
        'cpython',
        'click',
        'yourapplication',
        'flaskr',
        'blueprintexample',
        'jinja2',
        'urllib2',
        'simple_page',
        'pkg_resources'
    }


def test_local_hover():
    desired_result = {
        'contents': [
            {
                'language': 'python',
                'value': 'def find_best_app(param script_info, param module)'
            },
            'Given a module instance this tries to find the best possible\n'
            'application in the module or raises an exception.'
        ]
    }
    # hover over the definition
    result1 = flask_workspace.hover("/flask/cli.py", 34, 4)
    assert result1 == desired_result
    # hover over a usage
    result2 = flask_workspace.hover("/flask/cli.py", 215, 15)
    assert result2 == desired_result


def test_cross_module_hover():
    result = flask_workspace.hover("/flask/app.py", 220, 12)
    assert result == {
        'contents': [
            {
                'language': 'python',
                'value': 'class ConfigAttribute(param name, param '
                         'get_converter=None)'
            },
            'Makes an attribute forward to the config'
        ]
    }


def test_cross_package_hover():
    result = flask_workspace.hover("/flask/__init__.py", 44, 15)
    assert "contents" in result
    assert result["contents"]
    assert result["contents"][0] == {
                'language': 'python',
                'value': 'def jsonify(param *args, param **kwargs)'
            }


# TODO(aaron): the actual definition results have duplicates for some reason ... maybe the TestFileSystem?
def test_local_definition():
    result = flask_workspace.definition("/flask/cli.py", 215, 15)
    symbol = {
        'location': {
            'range': {
                'end': {
                    'character': 17,
                    'line': 34
                },
                'start': {
                    'character': 4,
                    'line': 34
                }
            },
            'uri': 'file:///flask/cli.py'
        },
        'symbol': {
            'container': 'flask.cli',
            'file': 'cli.py',
            'kind': 'def',
            'name': 'find_best_app',
            'package': {
                'name': 'flask'
            },
            'position': {
                'character': 4,
                'line': 34
            }
        }
    }
    assert symbol in result


def test_cross_module_definition():
    result = flask_workspace.definition("/flask/app.py", 220, 12)
    symbol = {
        'location': {
            'range': {
                'end': {
                    'character': 43,
                    'line': 26
                },
                'start': {
                    'character': 28,
                    'line': 26
                }
            },
            'uri': 'file:///flask/app.py'
        },
        'symbol': {
            'container': 'flask.app',
            'file': 'app.py',
            'kind': 'class',
            'name': 'ConfigAttribute',
            'package': {
                'name': 'flask'
            },
            'position': {
                'character': 28,
                'line': 26
            }
        }
    }
    assert symbol in result


def test_cross_package_definition():
    result = flask_workspace.definition("/flask/__init__.py", 44, 15)
    symbol = {
        'symbol': {
            'package': {
                'name': 'flask'
            },
            'name': 'jsonify',
            'container': 'flask.json',
            'kind': 'def',
            'file': '__init__.py',
            'position': {
                'line': 202,
                'character': 4
            }
        },
        'location': {
            'uri': 'file:///flask/json/__init__.py',
            'range': {
                'start': {
                    'line': 202,
                    'character': 4
                },
                'end': {
                    'line': 202,
                    'character': 11
                }
            }
        }
    }
    assert symbol in result


def test_local_package_import_definition():
    result = flask_workspace.definition("/flask/__init__.py", 44, 10)
    assert result == [
        {
            'symbol': {
                'package': {
                    'name': 'flask'
                },
                'name': 'json',
                'container': 'flask',
                'kind': 'module',
                'file': '__init__.py',
                'position': {
                    'line': 40,
                    'character': 14
                }
            },
            'location': {
                'uri': 'file:///flask/__init__.py',
                'range': {
                    'start': {
                        'line': 40,
                        'character': 14
                    },
                    'end': {
                        'line': 40,
                        'character': 18
                    }
                }
            }
        },
    ]


def test_cross_repo_hover():
    result = flask_workspace.hover("/flask/app.py", 295, 20)
    assert result == {
        'contents': [
            {
                'language': 'python',
                'value': 'class ImmutableDict(param type(self))'
            },
            'An immutable :class:`dict`.\n\n.. versionadded:: 0.5'
        ]
    }


def test_cross_repo_definition():
    result = flask_workspace.definition("/flask/app.py", 295, 20)
    # TODO(aaron): should we return a symbol descriptor with the local result? Might screw up xrefs
    assert result == [
        {
            'symbol': {
                'package': {
                    'name': 'werkzeug'
                },
                'name': 'ImmutableDict',
                'container': 'werkzeug.datastructures',
                'kind': 'class',
                'file': 'datastructures.py',
                'position': {
                    'line': 1536,
                    'character': 6
                }
            },
            'location': None
        },
        {
            'symbol': {
                'package': {
                    'name': 'flask'
                },
                'name': 'ImmutableDict',
                'container': 'flask.app',
                'kind': 'class',
                'file': 'app.py',
                'position': {
                    'line': 18,
                    'character': 36
                }
            },
            'location': {
                'uri': 'file:///flask/app.py',
                'range': {
                    'start': {
                        'line': 18,
                        'character': 36
                    },
                    'end': {
                        'line': 18,
                        'character': 49
                    }
                }
            }
        },
    ]


def test_cross_repo_import_definition():
    result = flask_workspace.definition("/flask/__init__.py", 18, 19)
    assert result == [
        {
            'symbol': {
                'package': {
                    'name': 'markupsafe'
                },
                'name': 'Markup',
                'container': 'markupsafe',
                'kind': 'class',
                'file': '__init__.py',
                'position': {
                    'line': 25,
                    'character': 6
                }
            },
            'location': None
        }
    ]


def test_stdlib_hover():
    result = flask_workspace.hover("/flask/app.py", 306, 48)
    assert result == {
        'contents': [
            {
                'language': 'python',
                'value': 'class timedelta(param type(self))'
            },
            'Represent the difference between two datetime objects.\n\n'
            'Supported operators:\n\n'
            '- add, subtract timedelta\n'
            '- unary plus, minus, abs\n'
            '- compare to timedelta\n'
            '- multiply, divide by int\n\n'
            'In addition, datetime supports subtraction of two datetime objects\n'
            'returning a timedelta, and addition or subtraction of a datetime\n'
            'and a timedelta giving a datetime.\n\n'
            'Representation: (days, seconds, microseconds).  Why?  Because I\n'
            'felt like it.'
        ]
    }


def test_stdlib_definition():
    result = flask_workspace.definition("/flask/app.py", 306, 48)[0]
    res = (result["location"]["uri"], result["location"]["range"]["start"]["line"], result["location"]["range"]["start"]["character"])
    defs = [
        {
            'symbol': {
                'package': {
                    'name': 'cpython'
                },
                'name': 'timedelta',
                'container': 'datetime',
                'kind': 'class',
                'path': 'Lib/datetime.py',
                'file': 'datetime.py',
                'position': {
                    'line': 335,
                    'character': 6
                }
            },
            'location': None
        },
        {
            'symbol': {
                'package': {
                    'name': 'flask'
                },
                'name': 'timedelta',
                'container': 'flask.app',
                'kind': 'class',
                'file': 'app.py',
                'position': {
                    'line': 13,
                    'character': 21
                }
            },
            'location': {
                'uri': 'file:///flask/app.py',
                'range': {
                    'start': {
                        'line': 13,
                        'character': 21
                    },
                    'end': {
                        'line': 13,
                        'character': 30
                    }
                }
            }
        },
    ]
    check_defs(res, defs)

def check_defs(start_location, defs):
    current_location = start_location
    for i in range(len(defs) - 1):
        file, line, col = start_location
        file = file.replace("http://","")
        result = flask_workspace.definition(file, line, col)[0]
        assert result == defs[i]
        current_location = (result["symbol"]["file"], result["symbol"]["position"]["line"], result["symbol"]["position"]["character"])

def test_local_references():
    result = flask_workspace.references("/flask/cli.py", 34, 4)
    assert result == [
        {
            'uri': 'file:///flask/cli.py',
            'range': {
                'start': {
                    'line': 215,
                    'character': 15
                },
                'end': {
                    'line': 215,
                    'character': 28
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 46,
                    'character': 11
                },
                'end': {
                    'line': 46,
                    'character': 24
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 51,
                    'character': 11
                },
                'end': {
                    'line': 51,
                    'character': 24
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 56,
                    'character': 11
                },
                'end': {
                    'line': 56,
                    'character': 24
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 63,
                    'character': 22
                },
                'end': {
                    'line': 63,
                    'character': 35
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 64,
                    'character': 11
                },
                'end': {
                    'line': 64,
                    'character': 24
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 71,
                    'character': 22
                },
                'end': {
                    'line': 71,
                    'character': 35
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 72,
                    'character': 11
                },
                'end': {
                    'line': 72,
                    'character': 24
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 79,
                    'character': 22
                },
                'end': {
                    'line': 79,
                    'character': 35
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 80,
                    'character': 11
                },
                'end': {
                    'line': 80,
                    'character': 24
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 87,
                    'character': 22
                },
                'end': {
                    'line': 87,
                    'character': 35
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 88,
                    'character': 11
                },
                'end': {
                    'line': 88,
                    'character': 24
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 97,
                    'character': 11
                },
                'end': {
                    'line': 97,
                    'character': 24
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 106,
                    'character': 11
                },
                'end': {
                    'line': 106,
                    'character': 24
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 111,
                    'character': 34
                },
                'end': {
                    'line': 111,
                    'character': 47
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 117,
                    'character': 34
                },
                'end': {
                    'line': 117,
                    'character': 47
                }
            }
        },
        {
            'uri': 'file:///tests/test_cli.py',
            'range': {
                'start': {
                    'line': 124,
                    'character': 34
                },
                'end': {
                    'line': 124,
                    'character': 47
                }
            }
        }
    ]


def test_x_references():
    result = flask_workspace.x_references("werkzeug.datastructures", "ImmutableDict")
    assert result == [
        {
            'reference': {
                'uri': 'file:///flask/app.py',
                'range': {
                    'start': {
                        'line': 18,
                        'character': 0
                    },
                    'end': {
                        'line': 18,
                        'character': 13
                    }
                }
            },
            'symbol': {
                'container': 'werkzeug.datastructures',
                'name': 'ImmutableDict'
            }
        },
        {
            'reference': {
                'uri': 'file:///flask/app.py',
                'range': {
                    'start': {
                        'line': 295,
                        'character': 20
                    },
                    'end': {
                        'line': 295,
                        'character': 33
                    }
                }
            },
            'symbol': {
                'container': 'werkzeug.datastructures',
                'name': 'ImmutableDict'
            }
        },
        {
            'reference': {
                'uri': 'file:///flask/app.py',
                'range': {
                    'start': {
                        'line': 300,
                        'character': 21
                    },
                    'end': {
                        'line': 300,
                        'character': 34
                    }
                }
            },
            'symbol': {
                'container': 'werkzeug.datastructures',
                'name': 'ImmutableDict'
            }
        }
    ]


def test_definition_of_definition():
    result = flask_workspace.definition("/flask/blueprints.py", 142, 8)
    assert result == [
        {
            'symbol': {
                'package': {
                    'name': 'flask'
                },
                'name': 'record_once',
                'container': 'flask.blueprints',
                'kind': 'def',
                'file': 'blueprints.py',
                'position': {
                    'line': 142,
                    'character': 8
                }
            },
            'location': {
                'uri': 'file:///flask/blueprints.py',
                'range': {
                    'start': {
                        'line': 142,
                        'character': 8
                    },
                    'end': {
                        'line': 142,
                        'character': 19
                    }
                }
            }
        }
    ]