from .harness import Harness
import uuid
import pytest


@pytest.fixture
def workspace():
    graphql_core_workspace = Harness("repos/graphql-core")
    graphql_core_workspace.initialize(
        "git://github.com/plangrid/graphql-core?" + str(uuid.uuid4()))
    yield graphql_core_workspace
    graphql_core_workspace.exit()


class TestGraphqlCore:
    def test_relative_import_definition(self, workspace):
        result = workspace.definition("/graphql/__init__.py", 52, 8)

        assert len(result) == 2
        assert all(["location" in d for d in result])

        result_locations = [d["location"] for d in result]

        definition_location = {
            'uri': 'file:///graphql/type/definition.py',
            'range': {
                'start': {
                    'line': 138,
                    'character': 6
                },
                'end': {
                    'line': 138,
                    'character': 23
                }
            }
        }

        # re-exported in the __init__ file for the defining package
        re_exported_location = {
            'uri': 'file:///graphql/type/__init__.py',
            'range': {
                'start': {
                    'line': 3,
                    'character': 4
                },
                'end': {
                    'line': 3,
                    'character': 21
                }
            }
        }

        assert definition_location in result_locations
        assert re_exported_location in result_locations
