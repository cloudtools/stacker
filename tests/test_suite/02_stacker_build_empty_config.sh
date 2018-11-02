#!/usr/bin/env bash

source ../test_helper.bash

stacker build <(echo "")
assert ! "$status" -eq 0
assert_has_line 'stacker.exceptions.InvalidConfig:'
