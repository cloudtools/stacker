.PHONY: build lint test-unit test-functional test ci

# Only run the functional tests on the master branch, since they can be slow.
ifeq ($(CIRCLE_BRANCH),master)
CI_TESTS = test-unit test-functional
else
CI_TESTS = test-unit
endif

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

# Target for CI tests. If building the master branch, this will also run the
# functional tests, which can be slow.
ci: $(CI_TESTS)

apidocs:
	sphinx-apidoc --force -o docs/api stacker
