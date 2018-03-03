from .harness import Harness
import pytest


@pytest.fixture()
def fizzbuzz_workspace():
    fizzbuzz_workspace = Harness("repos/fizzbuzz_service")
    fizzbuzz_workspace.initialize("repos/fizzbuzz_service")
    yield fizzbuzz_workspace
    fizzbuzz_workspace.exit()


class TestFizzBuzzWorkspace:
    # def test_x_packages(self, fizzbuzz_workspace):
    #     result = fizzbuzz_workspace.x_packages()

    #     assert len(result) == 7
    #     package = None
    #     for package in result:
    #         if "package" in package:
    #             if package["package"] == {'name': 'fizzbuzz_service'}:
    #                 break

    #     assert "package" in package
    #     assert package["package"] == {'name': 'fizzbuzz_service'}

    #     assert "dependencies" in package

    #     dependencies = {d["attributes"]["name"]
    #                     for d in package["dependencies"]}

    #     assert dependencies == {
    #         "setuptools",
    #         "cpython"
    #     }

    # def test_local_hover(self, fizzbuzz_workspace):
    #     uri = "file:///fizzbuzz_service/loopers/number_looper.py"
    #     line, col = 2, 7
    #     result = fizzbuzz_workspace.hover(uri, line, col)
    #     assert result == {
    #         'contents': [
    #             {
    #                 'language': 'python',
    #                 'value': 'class NumberLooper(param start, param end)'
    #             },
    #             'Very important class that is capable of gathering all the number strings '
    #             'in [start, end)'
    #         ]
    #     }

    # def test_local_package_cross_module_hover(self, fizzbuzz_workspace):
    #     uri = "file:///fizzbuzz_service/string_deciders/number_decider.py"
    #     line, col = 4, 22
    #     result = fizzbuzz_workspace.hover(uri, line, col)

    #     assert result == {
    #         'contents': [
    #             {
    #                 'language': 'python',
    #                 'value': 'def decide_output_for_number(param number)'
    #             },
    #             'Decides the output for a given number'
    #         ]
    #     }

    # def test_cross_package_hover(self, fizzbuzz_workspace):
    #     uri = "file:///fizzbuzz_service/checkers/fizzbuzz/fizzbuzz_checker.py"
    #     line, col = 5, 31
    #     result = fizzbuzz_workspace.hover(uri, line, col)
    #     assert result == {
    #         'contents': [
    #             {
    #                 'language': 'python',
    #                 'value': 'def should_fizz(param number)'
    #             },
    #             'Whether or not "fizz" should be printed for this number'
    #         ]
    #     }

    # def test_std_lib_hover(self, fizzbuzz_workspace):
    #     uri = "file:///fizzbuzz_service/__main__.py"
    #     line, col = 5, 10
    #     result = fizzbuzz_workspace.hover(uri, line, col)
    #     assert result == {
    #         'contents': [
    #             {
    #                 'language': 'python',
    #                 'value': 'def print(param value, param ..., param sep, param '
    #                 'end, param file, param flush)'
    #             },
    #             "print(value, ..., sep=' ', end='\\n', file=sys.stdout, "
    #             'flush=False)\n'
    #             '\n'
    #             'Prints the values to a stream, or to sys.stdout by default.\n'
    #             'Optional keyword arguments:\n'
    #             'file:  a file-like object (stream); defaults to the current '
    #             'sys.stdout.\n'
    #             'sep:   string inserted between values, default a space.\n'
    #             'end:   string appended after the last value, default a newline.\n'
    #             'flush: whether to forcibly flush the stream.'
    #         ]
    #     }

    # def test_local_defintion(self, fizzbuzz_workspace):
    #     uri = "/fizzbuzz_service/string_deciders/number_decision.py"
    #     line, col = 21, 21
    #     result = fizzbuzz_workspace.definition(uri, line, col)
    #     assert result == [
    #         {
    #             'symbol': {
    #                 'package': {
    #                     'name': 'fizzbuzz_service'
    #                 },
    #                 'name': 'OutputDecision',
    #                 'container': 'fizzbuzz_service.string_deciders.number_decision',
    #                 'kind': 'class',
    #                 'file': 'number_decision.py',
    #                 'position': {
    #                     'line': 5,
    #                     'character': 6
    #                 }
    #             },
    #             'location': {
    #                 'uri': 'file:///fizzbuzz_service/string_deciders/number_decision.py',
    #                 'range': {
    #                     'start': {
    #                         'line': 5,
    #                         'character': 6
    #                     },
    #                     'end': {
    #                         'line': 5,
    #                         'character': 20
    #                     }
    #                 }
    #             }
    #         }
    #     ]

    # def test_local_package_cross_module_definition(self, fizzbuzz_workspace):
    #     uri = "file:///fizzbuzz_service/string_deciders/number_decider.py"
    #     line, col = 4, 25
    #     result = fizzbuzz_workspace.definition(uri, line, col)
    #     definition = {
    #         'symbol': {
    #             'package': {
    #                 'name': 'fizzbuzz_service'
    #             },
    #             'name': 'decide_output_for_number',
    #             'container': 'fizzbuzz_service.string_deciders.number_decision',
    #             'kind': 'def',
    #             'file': 'number_decision.py',
    #             'position': {
    #                     'line': 12,
    #                     'character': 4
    #             }
    #         },
    #         'location': {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decision.py',
    #             'range': {
    #                 'start': {
    #                     'line': 12,
    #                     'character': 4
    #                 },
    #                 'end': {
    #                     'line': 12,
    #                     'character': 28
    #                 }
    #             }
    #         }
    #     }

    #     # from the import statement at the top of the file
    #     assignment = {
    #         'symbol': {
    #             'package': {
    #                 'name': 'fizzbuzz_service'
    #             },
    #             'name': 'decide_output_for_number',
    #             'container': 'fizzbuzz_service.string_deciders.number_decider',
    #             'kind': 'def',
    #             'file': 'number_decider.py',
    #             'position': {
    #                 'line': 0,
    #                 'character': 45
    #             }
    #         },
    #         'location': {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decider.py',
    #             'range': {
    #                 'start': {
    #                     'line': 0,
    #                     'character': 45
    #                 },
    #                 'end': {
    #                     'line': 0,
    #                     'character': 69
    #                 }
    #             }
    #         }
    #     }

    #     assert len(result) == 2

    #     assert definition in result
    #     assert assignment in result

    # def test_cross_package_definition(self, fizzbuzz_workspace):
    #     uri = "file:///fizzbuzz_service/checkers/fizzbuzz/fizzbuzz_checker.py"
    #     line, col = 5, 57
    #     result = fizzbuzz_workspace.definition(uri, line, col)

    #     definition = {
    #         'symbol': {
    #             'package': {
    #                 'name': 'fizzbuzz_service'
    #             },
    #             'name': 'should_buzz',
    #             'container': 'buzz.buzz_checker',
    #             'kind': 'def',
    #             'file': 'buzz_checker.py',
    #             'position': {
    #                 'line': 0,
    #                 'character': 4
    #             }
    #         },
    #         'location': {
    #             'uri': 'file:///fizzbuzz_service/checkers/buzz/buzz_checker.py',
    #             'range': {
    #                 'start': {
    #                     'line': 0,
    #                     'character': 4
    #                 },
    #                 'end': {
    #                     'line': 0,
    #                     'character': 15
    #                 }
    #             }
    #         }
    #     }

    #     # from the import statement at the top of the file
    #     assignment = {
    #         'symbol': {
    #             'package': {
    #                 'name': 'fizzbuzz_service'
    #             },
    #             'name': 'should_buzz',
    #             'container': 'fizzbuzz_service.checkers.fizzbuzz.fizzbuzz_checker',
    #             'kind': 'def',
    #             'file': 'fizzbuzz_checker.py',
    #             'position': {
    #                 'line': 1,
    #                 'character': 32
    #             },
    #         },
    #         'location': {
    #             'uri': 'file:///fizzbuzz_service/checkers/fizzbuzz/fizzbuzz_checker.py',
    #             'range': {
    #                 'start': {
    #                     'line': 1,
    #                     'character': 32
    #                 },
    #                 'end': {
    #                     'line': 1,
    #                     'character': 43
    #                 }
    #             }
    #         }
    #     }

    #     assert len(result) == 2

    #     assert definition in result
    #     assert assignment in result

    # def test_local_package_cross_module_import_definition(self, fizzbuzz_workspace):
    #     uri = "file:///fizzbuzz_service/string_deciders/number_decider.py"
    #     line, col = 0, 14
    #     result = fizzbuzz_workspace.definition(uri, line, col)

    #     assert len(result) == 1
    #     definition = result[0]

    #     assert "symbol" in definition
    #     assert definition["symbol"] == {
    #         'package': {
    #             'name': 'fizzbuzz_service'},
    #         'name': 'number_decision',
    #         'container': 'fizzbuzz_service.string_deciders.number_decision',
    #         'kind': 'module',
    #         'file': 'number_decision.py',
    #         'position': {
    #             'line': 0,
    #             'character': 0},
    #     }

    #     assert "location" in definition
    #     location = definition["location"]
    #     assert "uri" in location
    #     assert location["uri"] == 'file:///fizzbuzz_service/string_deciders/number_decision.py'

    #     # TODO: In the case of a module, does the range have any meaning?

    # def test_cross_package_import_definition(self, fizzbuzz_workspace):
    #     uri = "file:///fizzbuzz_service/loopers/number_looper.py"
    #     line, col = 0, 31
    #     result = fizzbuzz_workspace.definition(uri, line, col)

    #     assert len(result) == 1
    #     definition = result[0]

    #     assert "symbol" in definition
    #     assert definition["symbol"] == {
    #         'package': {
    #             'name': 'fizzbuzz_service'
    #         },
    #         'name': 'string_deciders',
    #         'container': 'fizzbuzz_service.string_deciders',
    #         'kind': 'module',
    #         'file': '__init__.py',
    #         'position': {
    #             'line': 0,
    #             'character': 0
    #         },
    #     }

    #     assert "location" in definition
    #     location = definition["location"]
    #     assert "uri" in location
    #     assert location["uri"] == 'file:///fizzbuzz_service/string_deciders/__init__.py'

    #     # TODO: In the case of a module, does the range have any meaning?

    def test_std_lib_definition(self, fizzbuzz_workspace):
        uri = 'file:///fizzbuzz_service/string_deciders/number_decision.py'
        line, col = 5, 23
        result = fizzbuzz_workspace.definition(uri, line, col)

        definition = {
            'symbol': {
                'package': {
                    'name': 'cpython'
                },
                'name': 'Enum',
                'container': 'enum',
                'kind': 'class',
                'path': 'Lib/enum.py',
                'file': 'enum.py',
                'position': {
                    'line': 508,
                    'character': 6
                },
            },
            'location': None
        }

        # from the import statement at the top of the file
        assignment = {
            'symbol': {
                'package': {
                    'name': 'fizzbuzz_service'
                },
                'name': 'Enum',
                'container': 'fizzbuzz_service.string_deciders.number_decision',
                'kind': 'class',
                'file': 'number_decision.py',
                'position': {
                    'line': 0,
                    'character': 17
                },
            },
            'location': {
                'uri': 'file:///fizzbuzz_service/string_deciders/number_decision.py',
                'range': {
                    'start': {
                        'line': 0,
                        'character': 17
                    },
                    'end': {
                        'line': 0,
                        'character': 21
                    }
                }
            }
        }

        import pdb
        pdb.set_trace()
        assert len(result) == 2

        assert definition in result
        assert assignment in result

    # def test_local_references(self, fizzbuzz_workspace):
    #     uri = 'file:///fizzbuzz_service/string_deciders/number_decision.py'
    #     line, col = 5, 13
    #     result = fizzbuzz_workspace.references(uri, line, col)

    #     references = [
    #         {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decider.py',
    #             'range': {
    #                 'start': {
    #                     'line': 6,
    #                     'character': 19
    #                 },
    #                 'end': {
    #                     'line': 6,
    #                     'character': 33
    #                 }
    #             }
    #         },
    #         {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decider.py',
    #             'range': {
    #                 'start': {
    #                     'line': 9,
    #                     'character': 19
    #                 },
    #                 'end': {
    #                     'line': 9,
    #                     'character': 33
    #                 }
    #             }
    #         },
    #         {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decider.py',
    #             'range': {
    #                 'start': {
    #                     'line': 12,
    #                     'character': 19
    #                 },
    #                 'end': {
    #                     'line': 12,
    #                     'character': 33
    #                 }
    #             }
    #         },
    #         {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decision.py',
    #             'range': {
    #                 'start': {
    #                     'line': 15,
    #                     'character': 15
    #                 },
    #                 'end': {
    #                     'line': 15,
    #                     'character': 29
    #                 }
    #             }
    #         },
    #         {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decision.py',
    #             'range': {
    #                 'start': {
    #                     'line': 18,
    #                     'character': 15
    #                 },
    #                 'end': {
    #                     'line': 18,
    #                     'character': 29
    #                 }
    #             }
    #         },
    #         {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decision.py',
    #             'range': {
    #                 'start': {
    #                     'line': 21,
    #                     'character': 15
    #                 },
    #                 'end':
    #                 {
    #                     'line': 21,
    #                     'character': 29
    #                 }
    #             }
    #         },
    #         {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decision.py',
    #             'range': {
    #                 'start': {
    #                     'line': 23,
    #                     'character': 11
    #                 },
    #                 'end': {
    #                     'line': 23,
    #                     'character': 25
    #                 }
    #             }
    #         },
    #     ]

    #     assert len(references) == len(result)
    #     for ref in references:
    #         assert ref in result

    # def test_x_references(self, fizzbuzz_workspace):
    #     result = fizzbuzz_workspace.x_references("enum", "Enum")

    #     import_ref = {
    #         'reference': {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decision.py',
    #             'range': {
    #                 'start': {
    #                     'line': 0,
    #                     'character': 0},
    #                 'end': {
    #                     'line': 0,
    #                     'character': 4}}},
    #         'symbol': {
    #             'container': 'enum',
    #             'name': 'Enum'}}

    #     base_class_ref = {
    #         'reference': {
    #             'uri': 'file:///fizzbuzz_service/string_deciders/number_decision.py',
    #             'range': {
    #                 'start': {
    #                     'line': 5,
    #                     'character': 21},
    #                 'end': {
    #                     'line': 5,
    #                     'character': 25}}},
    #         'symbol': {
    #             'container': 'enum',
    #             'name': 'Enum'}}

    #     assert len(result) == 2

    #     assert import_ref in result
    #     assert base_class_ref in result
