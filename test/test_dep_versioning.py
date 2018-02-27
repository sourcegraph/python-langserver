from .harness import Harness
import uuid
import pytest


@pytest.fixture()
def workspace():
    workspace = Harness("repos/dep_versioning")
    workspace.initialize("repos/dep_versioning?" + str(uuid.uuid4()))
    yield workspace
    workspace.exit()


"""
This test should pass as long as we do not fetch results from the correct version of dependencies .
Once we *do*, this test should be updated so the hover returns 'this is version 0.1'.
"""


class TestDependencyVersioning:
    def test_dep_version(self, workspace):
        uri = "file:///test.py"
        character, line = 6, 2
        result = workspace.hover(uri, line, character)
        assert result == {
            'contents': [
                {
                    'language': 'python',
                    'value': 'def testfunc()'
                },
                'this is version 0.1'
            ]
        }
