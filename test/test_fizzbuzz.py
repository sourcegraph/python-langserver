from .harness import Harness
import pytest

fizzbuzz_workspace = Harness("repos/fizzbuzz_service")
fizzbuzz_workspace.initialize("")

def test_x_packages():
    result = fizzbuzz_workspace.x_packages()

    assert len(result) == 1
    package = result[0]

    assert "package" in package
    assert package["package"] == {'name': 'fizzbuzz_service'}

    assert "dependencies" in package

    dependencies = {d["attributes"]["name"] for d in package["dependencies"]}

    assert dependencies == {"cpython"}


def test_local_hover():
    uri = "file:///fizzbuzz_service/loopers/number_looper.py"
    line, col = 2, 7
    result = fizzbuzz_workspace.hover(uri, line, col)
    assert result == {
        'contents': [
            {
                'language': 'python',
                'value': 'class NumberLooper(param start, param end)'
            },
            'Very important class that is capable of gathering all the number strings in [start, end)'
        ]
    }

def test_cross_package_hover():
    uri = "file:///fizzbuzz_service/checkers/fizzbuzz/fizzbuzz_checker.py"
    line, col = 5, 31
    result = fizzbuzz_workspace.hover(uri, line, col)
    assert result == {
        'contents': [
            {
                'language': 'python',
                'value': 'def should_fizz(param number)'
            },
            'Whether or not "fizz" should be printed for this number'
        ]
    }
