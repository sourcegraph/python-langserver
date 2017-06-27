from .harness import Harness, print_result
import uuid
import pytest


graphql_core_workspace = Harness("repos/graphql-core")
graphql_core_workspace.initialize("git://github.com/plangrid/graphql-core?" + str(uuid.uuid4()))


def test_relative_import_definition():
    result = graphql_core_workspace.definition("/graphql/__init__.py", 52, 8)
    assert result == [
        {
            'symbol': {
                'package': {
                    'name': 'graphql'
                },
                'name': 'GraphQLObjectType',
                'container': 'graphql.type.definition',
                'kind': 'class',
                'file': 'definition.py',
                'position': {
                    'line': 138,
                    'character': 6
                }
            },
            'location': {
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
        },
        {
            'symbol': {
                'package': {
                    'name': 'graphql'
                },
                'name': 'GraphQLObjectType',
                'container': 'graphql.type',
                'kind': 'class',
                'file': '__init__.py',
                'position': {
                    'line': 3,
                    'character': 4
                }
            },
            'location': {
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
        },
    ]


# TODO(aaron): not all relative imports work; seems to be a Jedi bug, as it appears in other Jedi-based extensions too
@pytest.mark.skip(reason="Jedi bug")
def test_relative_import_definition_broken():
    result = graphql_core_workspace.definition("/graphql/__init__.py", 52, 8)
    assert result == []
