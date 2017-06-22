from test.test_harness import TestFileSystem, TestHarness


flask_workspace = TestHarness("repos/flask")


def test_flask_local_hover():
    result = flask_workspace.hover("flask/cli.py", 34, 4)  # hover over the definition
    assert result == {
        'contents': [
            {
                'language': 'python',
                'value': 'def find_best_app(param script_info, param module)'
            },
            'Given a module instance this tries to find the best possible\n'
            'application in the module or raises an exception.'
        ]
    }
    result = flask_workspace.hover("flask/cli.py", 215, 15) # hover over a usage
    assert result == {
        'contents': [
            {
                'language': 'python',
                'value': 'def find_best_app(param script_info, param module)'
            },
            'Given a module instance this tries to find the best possible\n'
            'application in the module or raises an exception.'
        ]
    }
