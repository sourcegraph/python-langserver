from .harness import Harness
import uuid
import pytest


@pytest.fixture
def workspace():
    jedi_workspace = Harness("repos/jedi")
    jedi_workspace.initialize(
        "git://github.com/davidhalter/jedi?" + str(uuid.uuid4()))
    yield jedi_workspace
    jedi_workspace.exit()


class TestJedi:
    # def test_x_packages(self, workspace):
    #     packages = workspace.x_packages()
    #     assert packages
    #     result = None
    #     for p in packages:
    #         if "package" in p and p["package"] == {"name": "jedi"}:
    #             result = p
    #             break
    #     assert result
    #     assert "package" in result and result["package"] == {'name': 'jedi'}
    #     assert "dependencies" in result
    #     dep_names = {d["attributes"]["name"] for d in result["dependencies"]}
    #     assert dep_names == {
    #         'pytest',
    #         'not_in_sys_path',
    #         'numpy',
    #         '__main__',
    #         'import_tree',
    #         'recurse_class2',
    #         'not_existing',
    #         'psutil',
    #         'rename1',
    #         'local_module',
    #         'objgraph',
    #         'django',
    #         'cpython',
    #         'pylab',
    #         'docopt',
    #         'recurse_class1',
    #         'psycopg2',
    #         'not_existing_nested',
    #         'pygments'
    #     }

    def test_absolute_import_definition(self, workspace):
        result = workspace.definition("/jedi/api/__init__.py", 28, 26)

        assert len(result) == 1
        definition = result[0]

        assert "location" in definition
        assert definition["location"] == {
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
