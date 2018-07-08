#!/usr/bin/env bats

load ../test_helper

@test "stacker build - locked stacks" {
  needs_aws

  config1() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  }

  config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    locked: true
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    variables:
      StringVariable: \${output vpc::DummyId}
EOF
  }

  teardown() {
    stacker destroy --force <(config2)
  }

  stacker build <(config2)
  assert "$status" -eq 1
  assert_has_line "AttributeError: Stack does not have a defined class or template path."

  # Create the new stacks.
  stacker build <(config1)
  assert "$status" -eq 0

  stacker build <(config2)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "vpc: skipped (locked)"
  assert_has_line "bastion: submitted (creating new stack)"
  assert_has_line "bastion: complete (creating new stack)"
}
