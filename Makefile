.PHONY: build lint test-unit test-functional test

build:
	docker build -t remind101/stacker .

lint:
	flake8 --exclude stacker/tests/ stacker
	flake8 --ignore N802 stacker/tests # ignore setUp naming

test-unit:
	AWS_DEFAULT_REGION=us-east-1 python setup.py nosetests

test-functional:
	cd tests && bats .

# General testing target for most development.
test: lint test-unit

apidocs:
	sphinx-apidoc --force -o docs/api stacker
