from .harness import Harness
import uuid
import pytest


@pytest.fixture()
def workspace():
    workspace = Harness("repos/dep_versioning")
    workspace.initialize("repos/dep_versioning?" + str(uuid.uuid4()))
    yield workspace
    workspace.exit()

class TestDependencyVersioning:
    def test_dep_download_older_version(self, workspace):
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
