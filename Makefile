.PHONY: test

test:
	pytest test_langserver.py
	cd ./test && pytest test_*.py
