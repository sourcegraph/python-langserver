#!/usr/bin/env python3.5

import argparse
import sys
import jedi
import json


def hover(args):
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


def definition(args):
	source = open(args.path, "r").read()
	script = jedi.api.Script(source=source, line=args.line, column=args.column, path=args.path)

	for a in script.goto_assignments():
		if not a.is_definition():
			continue

		json.dump({
			"path": a.module_path,
			"line": a.line,
			"column": a.column,
		}, sys.stdout, sort_keys=True)
		sys.exit(0)
		break

	print("No definition found")


def references(args):
	source = open(args.path, "r").read()
	script = jedi.api.Script(source=source, line=args.line, column=args.column, path=args.path)

	usages = script.usages()
	if len(usages) == 0:
		print("No references found")
		return

	results = []
	for u in usages:
		if u.is_definition():
			continue

		results.append({
			"path": u.module_path,
			"line": u.line,
			"column": u.column,
		})

	json.dump(results, sys.stdout, sort_keys=True)


def main():
	parser = argparse.ArgumentParser(description="")
	parser.add_argument('--path', help='The path of the file in the file system.', default="")
	parser.add_argument('--line', help='The line to perform actions on (starting with 1).', default=1, type=int)
	parser.add_argument('--column', help='The column of the cursor (starting with 0).', default=0, type=int)

	subparsers = parser.add_subparsers(help="", dest="subcmd")
	hover_parser = subparsers.add_parser("hover", help="")
	definition_parser = subparsers.add_parser("definition", help="")
	references_parser = subparsers.add_parser("references", help="")

	args = parser.parse_args()
	if args.path == "":
		print("ls-python: --path is empty")
		sys.exit(2)
	elif args.line < 1:
		print("ls-python: --line is not valid")
		sys.exit(2)
	elif args.column < 0:
		print("ls-python: --column is not valid")
		sys.exit(2)

	if args.subcmd == "hover":
		hover(args)
	elif args.subcmd == "definition":
		definition(args)
	elif args.subcmd == "references":
		references(args)
	else:
		print("Sorry, I don't understand..")


if __name__ == '__main__':
	main()
