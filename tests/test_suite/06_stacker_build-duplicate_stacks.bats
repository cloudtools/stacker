#!/usr/bin/env bats

load ../test_helper

@test "stacker build - duplicate stacks" {
  stacker build - <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.VPC
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  assert ! "$status" -eq 0
  assert_has_line "Duplicate stack vpc found"
}
