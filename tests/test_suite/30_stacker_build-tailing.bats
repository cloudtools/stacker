#!/usr/bin/env bats

load ../test_helper

@test "stacker build - tailing" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    requires: [vpc]
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build --tail <(config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "Tailing stack: ${STACKER_NAMESPACE}-vpc"
  assert_has_line "vpc: submitted (creating new stack)"
  assert_has_line "vpc: complete (creating new stack)"
  assert_has_line "Tailing stack: ${STACKER_NAMESPACE}-bastion"
  assert_has_line "bastion: submitted (creating new stack)"
  assert_has_line "bastion: complete (creating new stack)"

  stacker destroy --force --tail <(config)
  assert "$status" -eq 0
}
