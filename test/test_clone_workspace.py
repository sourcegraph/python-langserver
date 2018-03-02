from langserver.clone_workspace import CloneWorkspace
from langserver.fs import TestFileSystem
import delegator
import pytest


@pytest.fixture()
def test_data():
    repoPath = "repos/fizzbuzz_service"
    workspace = CloneWorkspace(TestFileSystem(repoPath), repoPath, repoPath)
    yield (workspace, repoPath)


class TestCloningWorkspace:
    def test_clone(self, test_data):
        workspace, repoPath = test_data

        c = delegator.run("diff -r {} {}".format(repoPath,
                                                 workspace.CLONED_PROJECT_PATH))
        assert c.out == ""
        assert c.err == ""
        assert c.return_code == 0
