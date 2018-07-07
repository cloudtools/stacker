#!/bin/sh

TEST_ARGS=$*

if [ -z "$TEST_ARGS" ]
then
    _TESTS="test_suite"
else
    for T in ${TEST_ARGS}
    do
        _TESTS="${_TESTS} test_suite/$(printf %02d ${T})_*"
    done
fi

echo "bats ${_TESTS}"

bats ${_TESTS}
