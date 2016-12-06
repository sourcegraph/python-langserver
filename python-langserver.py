#!/usr/local/bin/python3

import sys
import time
import traceback
import langserver.langserver

while True:
    try:
        langserver.langserver.main()
    except Exception as e:
        tb = traceback.format_exc()
        print("FATAL ERROR: {} {}".format(e, tb))
