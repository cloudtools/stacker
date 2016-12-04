.PHONY: build test lint

build:
	docker build -t remind101/stacker .

lint:
	flake8 --exclude stacker/tests/ stacker
	flake8 --ignore N802 stacker/tests # ignore setUp naming

test: lint
	python setup.py test
