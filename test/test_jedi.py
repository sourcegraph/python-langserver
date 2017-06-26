from .test_harness import TestHarness
import uuid

jedi_workspace = TestHarness("repos/jedi")
jedi_workspace.initialize("git://github.com/davidhalter/jedi?" + str(uuid.uuid4()))


def print_result(result):
    print("\nRESULT\n", result, "\n")


def test_x_packages():
    result = jedi_workspace.x_packages()
    assert result
    result = result[0]
    assert "package" in result and result["package"] == {'name': 'jedi'}
    assert "dependencies" in result
    dep_names = {d["attributes"]["name"] for d in result["dependencies"]}
    assert dep_names == {
        'pytest',
        'not_in_sys_path',
        'numpy',
        '__main__',
        'import_tree',
        'recurse_class2',
        'not_existing',
        'psutil',
        'rename1',
        'local_module',
        'objgraph',
        'django',
        'cpython',
        'pylab',
        'docopt',
        'recurse_class1',
        'psycopg2',
        'not_existing_nested',
        'pygments'
    }


def test_absolute_import_definiton():
    result = jedi_workspace.definition("/jedi/api/__init__.py", 28, 26)
    symbol = {
        'symbol': {
            'package': {
                'name': 'jedi'
            },
            'name': 'Evaluator',
            'container': 'jedi.evaluate',
            'kind': 'class',
            'file': '__init__.py',
            'position': {
                'line': 86,
                'character': 6
            }
        },
        'location': {
            'uri': 'file:///jedi/evaluate/__init__.py',
            'range': {
                'start': {
                    'line': 86,
                    'character': 6
                },
                'end': {
                    'line': 86,
                    'character': 15
                }
            }
        }
    }
    assert symbol in result
