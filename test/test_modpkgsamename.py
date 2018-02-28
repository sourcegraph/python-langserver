from .harness import Harness
import uuid
import pytest

@pytest.fixture()
def workspace():
    workspace = Harness("repos/dep_pkg_module_same_name")
    workspace.initialize("repos/dep_pkg_module_same_name" + str(uuid.uuid4()))
    yield workspace
    workspace.exit()

class TestExtPkgHasModuleWithSameName:
    def test_hover_pkg_module_same_name(self, workspace):
        uri = "file:///test.py"
        line, col = 2, 18
        result = workspace.hover(uri, line, col)
        assert result == {
            'contents': [
                {
                    'language': 'python', 
                    'value': 'def testfunc()'
                }, 
                'this is version 0.6'
            ]
        }