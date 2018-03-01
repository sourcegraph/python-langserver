from .harness import Harness
import uuid


thefuck_workspace = Harness("repos/thefuck")
thefuck_workspace.initialize(
    "git://github.com/nvbn/thefuck?" + str(uuid.uuid4()))


# make sure that the resulting locations don't refer to files on the local
# filesystem
def test_local_references():
    result = thefuck_workspace.references(
        "/thefuck/argument_parser.py", 22, 21)
    assert result == [
        {
            'uri': 'file:///thefuck/argument_parser.py',
            'range': {
                'start': {
                    'line': 18,
                    'character': 21
                },
                'end': {
                    'line': 18,
                    'character': 33
                }
            }
        },
        {
            'uri': 'file:///thefuck/argument_parser.py',
            'range': {
                'start': {
                    'line': 22,
                    'character': 21
                },
                'end': {
                    'line': 22,
                    'character': 33
                }
            }
        },
        {
            'uri': 'file:///thefuck/argument_parser.py',
            'range': {
                'start': {
                    'line': 27,
                    'character': 21
                },
                'end': {
                    'line': 27,
                    'character': 33
                }
            }
        },
        {
            'uri': 'file:///thefuck/argument_parser.py',
            'range': {
                'start': {
                    'line': 32,
                    'character': 21
                },
                'end': {
                    'line': 32,
                    'character': 33
                }
            }
        },
        {
            'uri': 'file:///thefuck/argument_parser.py',
            'range': {
                'start': {
                    'line': 36,
                    'character': 21
                },
                'end': {
                    'line': 36,
                    'character': 33
                }
            }
        },
        {
            'uri': 'file:///thefuck/argument_parser.py',
            'range': {
                'start': {
                    'line': 40,
                    'character': 21
                },
                'end': {
                    'line': 40,
                    'character': 33
                }
            }
        },
        {
            'uri': 'file:///thefuck/argument_parser.py',
            'range': {
                'start': {
                    'line': 48,
                    'character': 14
                },
                'end': {
                    'line': 48,
                    'character': 26
                }
            }
        },
        {
            'uri': 'file:///thefuck/argument_parser.py',
            'range': {
                'start': {
                    'line': 52,
                    'character': 14
                },
                'end': {
                    'line': 52,
                    'character': 26
                }
            }
        }
    ]
