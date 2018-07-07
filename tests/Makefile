permissions:
	./stacker.yaml.sh | stacker build -

test: permissions
	$(eval AWS_ACCESS_KEY_ID := $(shell ./stacker.yaml.sh | stacker info - 2>&1 | awk '/AccessKeyId/ {print $$3}'))
	$(eval AWS_SECRET_ACCESS_KEY := $(shell ./stacker.yaml.sh | stacker info - 2>&1 | awk '/SecretAccessKey/ {print $$3}'))
	$(eval STACKER_ROLE := $(shell ./stacker.yaml.sh | stacker info - 2>&1 | awk '/FunctionalTestRole/ {print $$3}'))
	@STACKER_ROLE=$(STACKER_ROLE) AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) ./run_test_suite.sh ${TESTS}
