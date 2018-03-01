.PHONY: test

init:
	pip install pipenv
	pipenv install --dev

lint:
	flake8

test:
	pipenv run pytest test_langserver.py
	cd ./test && pipenv run pytest test_*.py
