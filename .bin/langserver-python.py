#!/usr/bin/env python3.5

import argparse
import sys
import jedi
import json


def hover(args):
	if args.path == "":
		print("ls-python: --path is empty")
		sys.exit(2)
	elif args.line < 1:
		print("ls-python: --line is not valid")
		sys.exit(2)
	elif args.column < 0:
		print("ls-python: --column is not valid")
		sys.exit(2)

	source = open(args.path, "r").read()
	script = jedi.api.Script(source=source, line=args.line, column=args.column, path=args.path)

	for c in script.completions():
		docstring = c.docstring()
		if docstring == "":
			continue
		print(c.docstring())
		sys.exit(0)
		break

	print("No definition found")


def main():
	parser = argparse.ArgumentParser(description="")
	subparsers = parser.add_subparsers(help="", dest="subcmd")

	hover_parser = subparsers.add_parser("hover", help="")
	hover_parser.add_argument('--path', help='The path of the file in the file system.', default="")
	hover_parser.add_argument('--line', help='The line to perform actions on (starting with 1).', default=1, type=int)
	hover_parser.add_argument('--column', help='The column of the cursor (starting with 0).', default=0, type=int)

	args = parser.parse_args()
	if args.subcmd == "hover":
		hover(args)
	else:
		print("Sorry, I don't understand..")


if __name__ == '__main__':
	main()
