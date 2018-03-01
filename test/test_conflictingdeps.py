from .harness import Harness
import uuid
import pytest


@pytest.fixture()
def workspace():
    workspace = Harness("repos/confl_dep")
    workspace.initialize("repos/confl_dep?" + str(uuid.uuid4()))
    yield workspace
    workspace.exit()


class TestConflictingDependencies:
    def test_hover_packages_conflicting_module_names(self, workspace):
        uri = "file:///confl_dep/__main__.py"

        # django import
        d_line, d_col = 0, 11
        d_result = workspace.hover(uri, d_line, d_col)
        assert d_result == {
            'contents': [
                {
                    'language': 'python',
                    'value': 'django'
                }
            ]
        }

        # jinja2 import
        j_line, j_col = 1, 11
        j_result = workspace.hover(uri, j_line, j_col)
        assert j_result == {
            'contents': [
                {
                    'language': 'python',
                    'value': 'jinja2'
                },
                'jinja2\n'
                '~~~~~~\n'
                '\n'
                'Jinja2 is a template engine written in pure Python.  It '
                'provides a\n'
                'Django inspired non-XML syntax but supports inline expressions '
                'and\n'
                'an optional sandboxed environment.\n'
                '\n'
                'Nutshell\n'
                '--------\n'
                '\n'
                'Here a small example of a Jinja2 template::\n'
                '\n'
                "    {% extends 'base.html' %}\n"
                '    {% block title %}Memberlist{% endblock %}\n'
                '    {% block content %}\n'
                '      <ul>\n'
                '      {% for user in users %}\n'
                '        <li><a href="{{ user.url }}">{{ user.username '
                '}}</a></li>\n'
                '      {% endfor %}\n'
                '      </ul>\n'
                '    {% endblock %}\n'
                '\n'
                '\n'
                ':copyright: (c) 2017 by the Jinja Team.\n'
                ':license: BSD, see LICENSE for more details.'
            ]
        }
