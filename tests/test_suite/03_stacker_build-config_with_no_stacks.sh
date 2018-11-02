#!/usr/bin/env bash

source ../test_helper.bash

needs_aws

stacker build - <<EOF
namespace: ${STACKER_NAMESPACE}
EOF
assert "$status" -eq 0
assert_has_line 'WARNING: No stacks detected (error in config?)'
