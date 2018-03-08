from .harness import Harness
import uuid
import pytest


@pytest.fixture
def workspace():
    tensorflow_models_workspace = Harness("repos/tensorflow-models")
    tensorflow_models_workspace.initialize(
        "git://github.com/tensorflow/models?" + str(uuid.uuid4()))
    yield tensorflow_models_workspace
    tensorflow_models_workspace.exit()


class TestTensorflowModels:
    def test_namespace_package_definition(self, workspace):
        result = workspace.definition(
            "/inception/inception/flowers_eval.py", 23, 22)

        assert len(result) == 1
        definition = result[0]

        assert "location" in definition
        definition["location"] == {
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

    def test_ad_hoc_module_definition(self, workspace):
        result = workspace.definition(
            "/skip_thoughts/skip_thoughts/evaluate.py", 43, 26)

        assert len(result) == 1
        definition = result[0]

        assert "location" in definition
        definition["location"] == {
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
