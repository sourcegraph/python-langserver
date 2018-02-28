from .harness import Harness
import uuid
import pytest


@pytest.fixture()
def workspace():
    workspace = Harness("repos/dep_versioning_hierarchy")
    workspace.initialize("repos/dep_versioning_hierarchy" + str(uuid.uuid4()))
    yield workspace

    workspace.exit()

class TestDependencyVersioningHierarchy:
    def test_req_file_in_same_subproject(self, workspace):
        test_cases = [
            ("file:///sub_project_1/test.py", "this is version 0.1"),
            ("file:///sub_project_2/test.py", "this is version 0.2")
        ]

        for uri, expected_doc_string in test_cases:
            char, line = 6, 2
            result = workspace.hover(uri, line, char)
            assert result == {
            'contents': [
                {
                    'language': 'python',
                    'value': 'def testfunc()'
                },
                expected_doc_string
            ]
        }

    def test_req_file_in_parent(self, workspace):
        uri = "file:///sub_project_no_req/test.py"
        char, line = 6, 2
        result = workspace.hover(uri, line, char)
        assert result == {
            'contents': [
                {
                    'language': 'python',
                    'value': 'def testfunc()'
                },
                "this is version 0.5"
            ]
        }