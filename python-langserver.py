#!/usr/local/bin/python3

import os.path
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from langserver.langserver import main  # noqa: E402

if __name__ == '__main__':
    main()
