#!/usr/bin/env bash

source ../test_helper.bash

stacker build - <<EOF
stacker_bucket: stacker-${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.VPC
EOF
assert ! "$status" -eq 0
assert_has_line "This field is required"
