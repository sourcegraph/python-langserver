from .harness import Harness
import uuid


tensorflow_models_workspace = Harness("repos/tensorflow-models")
tensorflow_models_workspace.initialize(
    "git://github.com/tensorflow/models?" + str(uuid.uuid4()))


def test_namespace_package_definition():
    result = tensorflow_models_workspace.definition(
        "/inception/inception/flowers_eval.py", 23, 22)
    symbol = {
        'symbol': {
            'package': {
                'name': 'inception_eval'
            },
            'name': 'inception_eval',
            'container': 'inception_eval',
            'kind': 'module',
            'file': 'inception_eval.py',
            'position': {
                'line': 0,
                'character': 0
            }
        },
        'location': {
            'uri': 'file:///inception/inception/inception_eval.py',
            'range': {
                'start': {
                    'line': 0,
                    'character': 0
                },
                'end': {
                    'line': 0,
                    'character': 14
                }
            }
        }
    }
    assert symbol in result


def test_ad_hoc_module_definition():
    result = tensorflow_models_workspace.definition(
        "/skip_thoughts/skip_thoughts/evaluate.py", 43, 26)
    symbol = {
        'symbol': {
            'package': {
                'name': 'skip_thoughts'
            },
            'name': 'encoder_manager',
            'container': 'skip_thoughts.encoder_manager',
            'kind': 'module',
            'file': 'encoder_manager.py',
            'position': {
                'line': 0,
                'character': 0
            }
        },
        'location': {
            'uri': 'file:///skip_thoughts/skip_thoughts/encoder_manager.py',
            'range': {
                'start': {
                    'line': 0,
                    'character': 0
                },
                'end': {
                    'line': 0,
                    'character': 15
                }
            }
        }
    }
    assert symbol in result
