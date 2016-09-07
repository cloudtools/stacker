.PHONY: build

build:
	docker build -t remind101/stacker .

test:
	flake8 --exclude stacker/tests/ stacker
	flake8 --ignore N802 stacker/tests # ignore setUp naming
	python setup.py test
