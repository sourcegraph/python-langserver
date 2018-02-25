.PHONY: test

init:
	pip install pipenv
    pipenv install --dev

test:
	pipenv run pytest test_langserver.py
	cd ./test && pipenv run pytest test_*.py
