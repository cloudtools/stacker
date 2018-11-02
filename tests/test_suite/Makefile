TESTS := $(shell ls *.sh)

test: $(TESTS)
	parallel bash ::: $^
