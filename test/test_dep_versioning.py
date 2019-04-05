from .harness import Harness
import uuid
import pytest


@pytest.fixture(params=[
    # tuples of the repo for the test, along
    # with the expected doc_string for the hover
    # in that repo
    ("repos/dep_versioning_fixed", "this is version 0.1"),
    ("repos/dep_versioning_between", "this is version 0.4"),
    ("repos/dep_versioning_between_multiple", "this is version 0.4"),
])
def test_data(request):
    repo_path, expected_doc_string = request.param

    workspace = Harness(repo_path)
    workspace.initialize(repo_path + str(uuid.uuid4()))
    yield (workspace, expected_doc_string)

    workspace.exit()


@pytest.fixture
def workspace_no_installation_file():
    workspace = Harness("repos/dep_versioning_none")
    workspace.initialize("repos/dep_versioning_none" + str(uuid.uuid4()))
    yield workspace
    workspace.exit()


class TestDependencyVersioning:

    def test_dep_download_specified_version(self, test_data):
        workspace, expected_doc_string = test_data

        uri = "file:///test.py"
        character, line = 6, 2

        result = workspace.hover(uri, line, character)
        assert result == {
            'contents': [
                {
                    'language': 'python',
                    'value': 'def testfunc()'
                },
                expected_doc_string
            ]
        }

    def test_dep_no_installation_files(self, workspace_no_installation_file):
        # no setup.py, *requirements.txt, or Pipfile present in the project

        uri = "file:///test.py"
        character, line = 6, 2

        result = workspace_no_installation_file.hover(
            uri, line, character)
        assert result == {
            'contents': [
                {
                    'language': 'python',
                    'value': 'testfunc'
                }
            ]
        }
