# from .harness import Harness

# workspace = Harness("repos/global-variables")
# workspace.initialize("")


# def test_name_definition():
#     # The __name__ global variable should resolve to a symbol without
#     # a corresponding location
#     uri = "file:///name_global.py"
#     line, col = 0, 4

#     result = workspace.definition(uri, line, col)
#     assert result == [
#         {
#             'symbol':
#             {
#                 'package': {
#                     'name': 'name_global'
#                 },
#                 'name': '__name__',
#                 'container': 'name_global',
#                 'kind': 'instance',
#                 'file': 'name_global.py'
#             },
#             'location': None
#         }
#     ]
