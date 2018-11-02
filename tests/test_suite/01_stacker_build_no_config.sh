#!/usr/bin/env bash

source ../test_helper.bash

stacker build
assert ! "$status" -eq 0
assert_has_line -E "too few arguments|the following arguments are required: config"
